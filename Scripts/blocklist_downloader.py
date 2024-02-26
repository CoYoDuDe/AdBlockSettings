#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import requests
import os

def get_dbus_setting_value(path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", path)
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.BusItem')
    value = settings_interface.GetValue()
    print(f"Value for path {path}: {value}")
    return value

def set_dbus_setting_value(path, value):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", "/Settings")
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    parts = path.rsplit('/', 1)
    group, name = parts[0], parts[1]
    byte_value = dbus.ByteArray(bytes.fromhex(value))
    settings_interface.AddSetting(group, name, byte_value, 'ay', dbus.ByteArray([0]*len(byte_value)), dbus.ByteArray([255]*len(byte_value)))
    print(f"MD5-Wert im D-Bus aktualisiert: {value}")

def convert_to_dnsmasq_format(lines):
    return ["address=/{}/".format(line.split()[1]) for line in lines if line]

def download_and_configure_ad_list():
    ad_list_url = get_dbus_setting_value("/Settings/AdBlock/AdListURL")
    response = requests.get(ad_list_url)
    file_path = "/etc/dnsmasq.d/AdList.conf"
    
    if response.status_code == 200:
        lines = response.text.strip().split('\n')
        dnsmasq_lines = convert_to_dnsmasq_format(lines)

        with open(file_path, "w") as f:
            f.write('\n'.join(dnsmasq_lines))

        print("Ad-List successfully downloaded and updated.")
    else:
        print("Download failed with status code:", response.status_code)

if __name__ == "__main__":
    download_and_configure_ad_list()
