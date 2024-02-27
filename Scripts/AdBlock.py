import argparse
import requests
from pathlib import Path
import dbus
import sys
import os
import subprocess
import hashlib
from dbus.mainloop.glib import DBusGMainLoop

# Importieren der VeDbusItemImport und VeDbusItemExport Klassen
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/data/AdBlockSettings'))
from vedbus import VeDbusItemExport, VeDbusItemImport

DBusGMainLoop(set_as_default=True)
dbus_system_bus = dbus.SystemBus()

# Globale Einstellungen
local_file_path = '/etc/dnsmasq.d/adblock.conf'
dnsmasq_config_path = "/etc/dnsmasq.conf"
static_dnsmasq_config_path = "/etc/dnsmasq_static.conf"
dbus_system_bus = dbus.SystemBus()

def get_dbus_setting_value(path):
    try:
        item = VeDbusItemImport(dbus_system_bus, 'com.victronenergy.settings', path)
        return item.get_value()
    except Exception as e:
        print(f"DBus Fehler: {e}")
        return None

def set_dbus_setting_value(path, value):
    try:
        item = VeDbusItemExport(dbus_system_bus, path, value, writeable=True)
        item.local_set_value(value)
        print(f"Wert für Pfad {path} im D-Bus aktualisiert: {value}")
    except Exception as e:
        print(f"Fehler beim Aktualisieren des D-Bus Wertes: {e}")

def update_cronjob():
    script_path = os.path.abspath(__file__)  # Korrektur für den Skriptpfad
    update_interval = get_dbus_setting_value("/Settings/AdBlock/UpdateInterval")
    cron_job_comment = "dnsmasq_adblock_update"
    command = f'python {script_path} --download'

    # Bestehenden Cronjob entfernen
    subprocess.call(['crontab', '-l', '|', 'grep', '-v', cron_job_comment, '|', 'crontab', '-'])

    # Neuen Job basierend auf dem Update-Intervall hinzufügen
    if update_interval == "daily":
        schedule = "@daily"
    elif update_interval == "weekly":
        schedule = "@weekly"
    elif update_interval == "monthly":
        schedule = "@monthly"
    else:
        return  # Ungültiges Intervall

    # Neuen Cronjob hinzufügen
    cron_job = f"{schedule} {command} # {cron_job_comment}\n"
    subprocess.call(['(crontab', '-l;', 'echo', f'"{cron_job}"', ')', '|', 'crontab', '-'])

    print("Cronjob für AdBlock-Listenupdate wurde aktualisiert.")

def calculate_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def convert_to_dnsmasq_format(lines):
    converted_lines = []
    for line in lines:
        if line.strip() and not line.startswith("#"):  # Überprüft, ob die Zeile nicht leer und kein Kommentar ist
            parts = line.split()  # Trennt die Zeile an Leerzeichen
            if len(parts) >= 2:  # Stellt sicher, dass die Zeile eine IP-Adresse und eine Domain enthält
                domain = parts[1]  # Die Domain ist der zweite Teil der Zeile (nach der IP-Adresse)
                converted_line = f"address=/{domain}/0.0.0.0"  # Formatierung für dnsmasq
                converted_lines.append(converted_line)
    return converted_lines

def download_adblock_list():
    print("Starte Download der AdBlock-Liste...")
    adblock_list_url = get_dbus_setting_value("/Settings/AdBlock/AdListURL")
    last_known_hash = get_dbus_setting_value("/Settings/AdBlock/LastKnownHash")

    try:
        response = requests.get(adblock_list_url, timeout=10)
        if response.status_code == 200:
            current_hash = calculate_hash(response.text)
            if current_hash != last_known_hash:
                converted_list = convert_to_dnsmasq_format(response.text.splitlines())
                with open(local_file_path, 'w') as file:
                    file.write("\n".join(converted_list))
                # Funktion zum Speichern des neuen Hash im dbus hinzufügen
                # set_dbus_setting_value("/Settings/AdBlock/LastKnownHash", current_hash)
                print("Download abgeschlossen und AdBlock-Liste aktualisiert.")
            else:
                print("AdBlock-Liste hat sich nicht geändert, kein Download erforderlich.")
        else:
            print(f"Fehler beim Download der AdBlock-Liste: HTTP {response.status_code}")
    except requests.RequestException as e:
        print(f"Download fehlgeschlagen: {e}")

def configure_dnsmasq():
    print("Starte Konfiguration von dnsmasq...")
    adblock_enabled = get_dbus_setting_value("/Settings/AdBlock/Enabled")
    dhcp_enabled = get_dbus_setting_value("/Settings/DHCP/Enabled")

    new_config = f"conf-file={static_dnsmasq_config_path}\n"

    if adblock_enabled:
        new_config += f"conf-file={local_file_path}\n"

    if dhcp_enabled:
        default_gateway = get_dbus_setting_value("/Settings/AdBlock/DefaultGateway")
        ip_range_start = get_dbus_setting_value("/Settings/AdBlock/IPRangeStart")
        ip_range_end = get_dbus_setting_value("/Settings/AdBlock/IPRangeEnd")
        dhcp_range = f"{ip_range_start},{ip_range_end},12h"
        new_config += f"dhcp-range={dhcp_range}\n"
        new_config += f"dhcp-option=option:router,{default_gateway}\n"

    ipv6_enabled = get_dbus_setting_value("/Settings/AdBlock/IPv6Enabled")
    if ipv6_enabled:
        new_config += "enable-ra\n"

    with open(dnsmasq_config_path, 'w') as file:
        file.write(new_config)

    print("dnsmasq-Konfiguration aktualisiert.")

def restart_dnsmasq():
    os.system("/etc/init.d/dnsmasq restart")
    print("dnsmasq-Dienst neu gestartet.")

def main():
    parser = argparse.ArgumentParser(description="Verwaltungsskript für dnsmasq.")
    parser.add_argument('--download', help='Download der AdBlock-Liste', action='store_true')
    parser.add_argument('--configure', help='Konfiguration von dnsmasq', action='store_true')
    parser.add_argument('--update-cron', help='Aktualisiere den Cronjob für AdBlock-Listenupdates', action='store_true')

    args = parser.parse_args()

    if args.download:
        download_adblock_list()

    if args.configure:
        configure_dnsmasq()

    if args.update_cron:
        update_cronjob()

    if args.download or args.configure:
        restart_dnsmasq()

    if not any([args.download, args.configure, args.update_cron]):
        print("Bitte geben Sie eine Aktion an (--download, --configure, --update-cron).")
        sys.exit(1)

if __name__ == "__main__":
    main()
