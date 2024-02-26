#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import requests
import hashlib
import os

def get_dbus_setting_value(path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", path)
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.BusItem')
    value = settings_interface.GetValue()
    if isinstance(value, dbus.ByteArray):
        return ''.join(format(byte, '02x') for byte in value)  # Konvertiert Byte-Array zu Hex-String
    return value

def set_dbus_setting_value(path, value):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", "/Settings")
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    parts = path.rsplit('/', 1)
    group, name = parts[0], parts[1]
    # Konvertieren Sie den Hex-String zu einem Byte-Array für die Speicherung im D-Bus
    byte_value = dbus.ByteArray(bytes.fromhex(value))
    settings_interface.AddSetting(group, name, byte_value, 'ay', dbus.ByteArray([0]*len(byte_value)), dbus.ByteArray([255]*len(byte_value)))
    print(f"MD5-Wert im D-Bus aktualisiert: {value}")

def calculate_md5(content):
    hash_md5 = hashlib.md5()
    hash_md5.update(content.encode('utf-8'))
    return hash_md5.hexdigest()

def convert_to_dnsmasq_format(lines):
    return ["address=/{}/".format(line.split()[1]) for line in lines if line]

def download_and_configure_ad_list():
    ad_list_url = get_dbus_setting_value("/Settings/AdBlock/AdListURL")
    response = requests.get(ad_list_url)
    file_path = "/etc/dnsmasq.d/AdList.conf"
    
    # Überprüfen, ob die Datei existiert
    file_exists = os.path.isfile(file_path)

    if response.status_code == 200:
        raw_content_md5 = calculate_md5(response.text)
        previous_raw_md5 = get_dbus_setting_value("/Settings/AdBlock/RawAdListMD5")

        # Aktualisieren, wenn der MD5-Wert unterschiedlich ist ODER die Datei nicht existiert
        if raw_content_md5 != previous_raw_md5 or not file_exists:
            lines = response.text.strip().split('\n')
            dnsmasq_lines = convert_to_dnsmasq_format(lines)

            with open(file_path, "w") as f:
                f.write('\n'.join(dnsmasq_lines))

            set_dbus_setting_value("/Settings/AdBlock/RawAdListMD5", raw_content_md5)

            print("Ad-List successfully downloaded, converted, and updated.")
        else:
            print("No changes detected in Ad-List.")
    else:
        print("Download failed with status code:", response.status_code)

if __name__ == "__main__":
    download_and_configure_ad_list()
