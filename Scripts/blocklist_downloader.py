import dbus
import requests
import hashlib
import os

def get_dbus_setting(service, path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object(service, '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    return settings_interface.GetValue(path)

def set_dbus_setting(service, path, value):
    bus = dbus.SystemBus()
    settings_service = bus.get_object(service, '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    settings_interface.SetValue(path, value)

def calculate_md5(content):
    hash_md5 = hashlib.md5()
    hash_md5.update(content.encode('utf-8'))
    return hash_md5.hexdigest()

def convert_to_dnsmasq_format(lines):
    return ["address=/{}/".format(line.split()[1]) for line in lines if line]

def download_and_configure_ad_list():
    ad_list_url = get_dbus_setting("com.victronenergy.settings", "/Settings/AdBlock/AdListURL")
    response = requests.get(ad_list_url)
    if response.status_code == 200:
        raw_content_md5 = calculate_md5(response.text)
        previous_raw_md5 = get_dbus_setting("com.victronenergy.settings", "/Settings/AdBlock/RawAdListMD5")

        if raw_content_md5 != previous_raw_md5:
            lines = response.text.strip().split('\n')
            dnsmasq_lines = convert_to_dnsmasq_format(lines)
            file_path = "/etc/dnsmasq.d/AdList.conf"

            with open(file_path, "w") as f:
                f.write('\n'.join(dnsmasq_lines))

            # Speichern des MD5-Werts der rohen Ad-Liste für zukünftige Vergleiche
            set_dbus_setting("com.victronenergy.settings", "/Settings/AdBlock/RawAdListMD5", raw_content_md5)

            print("Ad-List successfully downloaded, converted, and updated.")
        else:
            print("No changes detected in Ad-List.")
    else:
        print("Download failed with status code:", response.status_code)

if __name__ == "__main__":
    download_and_configure_ad_list()
