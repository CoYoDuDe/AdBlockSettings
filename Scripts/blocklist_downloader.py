import dbus
import requests
import hashlib
import os

def get_dbus_setting(service, path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object(service, '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    return settings_interface.GetValue(path)

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def download_and_process_blocklist(adlist_url, destination, dnsmasq_list_path):
    try:
        response = requests.get(adlist_url, allow_redirects=True)
        response.raise_for_status()
        downloaded_md5 = hashlib.md5(response.content).hexdigest()

        if os.path.isfile(destination):
            current_md5 = calculate_md5(destination)
        else:
            current_md5 = None

        if downloaded_md5 != current_md5:
            with open(destination, 'wb') as file:
                file.write(response.content)
            print("Blocklist updated.")

            with open(destination, 'r') as file, open(dnsmasq_list_path, 'w') as dnsmasq_file:
                for line in file:
                    if line.strip() and not line.startswith('#'):
                        domain = line.split()[1]
                        dnsmasq_file.write(f"address=/{domain}/\n")

            print("Blocklist processed for dnsmasq.")
            return True
        else:
            print("No update needed.")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error downloading blocklist: {e}")
        return False

# Einstellungen aus D-Bus auslesen
adblock_service = "com.victronenergy.settings"
adlist_url_path = "/Settings/AdBlock/AdListURL"

# URL der Blockliste aus D-Bus Einstellungen auslesen
adlist_url = get_dbus_setting(adblock_service, adlist_url_path)

# Feste Pfade für die Blockliste und die dnsmasq-Konfiguration
destination_path = "/path/to/adlist.txt"
dnsmasq_list_path = "/etc/dnsmasq.d/adblock_list.conf"

# Blockliste herunterladen und für dnsmasq verarbeiten
download_and_process_blocklist(adlist_url, destination_path, dnsmasq_list_path)
