import argparse
import requests
from pathlib import Path
import dbus
import os
import crontab
import hashlib

# Globale Einstellungen
local_file_path = '/etc/dnsmasq.d/adblock.conf'
dnsmasq_config_path = "/etc/dnsmasq.conf"
static_dnsmasq_config_path = "/etc/dnsmasq_static.conf"

def get_dbus_setting_value(path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", path)
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.BusItem')
    value = settings_interface.GetValue()
    return value

def update_cronjob():
    script_path = os.path.abspath(__file__)  # Korrektur für den Skriptpfad
    update_interval = get_dbus_setting_value("/Settings/AdBlock/UpdateInterval")
    cron = crontab.CronTab(user=True)
    cron_job_comment = "dnsmasq_adblock_update"

    # Bestehenden Cronjob entfernen
    cron.remove_all(comment=cron_job_comment)

    # Neuen Job basierend auf dem Update-Intervall hinzufügen
    job = cron.new(command=f'python {script_path} --download', comment=cron_job_comment)
    if update_interval == "daily":
        job.every().day()
    elif update_interval == "weekly":
        job.every().week()
    elif update_interval == "monthly":
        job.every().month()

    cron.write()
    print("Cronjob für AdBlock-Listenupdate wurde aktualisiert.")

def calculate_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def convert_to_dnsmasq_format(lines):
    return ["address=/{}/".format(line.strip()) for line in lines if line.strip() and not line.startswith("#")]

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
        dhcp_range = f"{ip_range_start},{ip_range_end},12h"  # Beispiel für die Lease-Zeit
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
