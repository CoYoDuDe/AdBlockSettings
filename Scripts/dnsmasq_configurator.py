#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import os

def get_dbus_setting_value(path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", path)
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.BusItem')
    value = settings_interface.GetValue()
    print(f"Value for path {path}: {value}")
    return value

def backup_and_clear_dnsmasq_config(main_config_path="/etc/dnsmasq.conf"):
    backup_config_path = f"{main_config_path}.orig"
    if not os.path.exists(backup_config_path):
        os.rename(main_config_path, backup_config_path)
        print(f"Original dnsmasq Konfiguration gesichert als {backup_config_path}")

def update_dnsmasq_config(main_config_path="/etc/dnsmasq.conf", adlist_config_path="/etc/dnsmasq.d/AdList.conf"):
    adblock_enabled = get_dbus_setting_value("/Settings/AdBlock/Enabled")
    dhcp_enabled = get_dbus_setting_value("/Settings/AdBlock/DHCPEnabled")
    ipv6_enabled = get_dbus_setting_value("/Settings/AdBlock/IPv6Enabled")

    if not os.path.exists(main_config_path):
        open(main_config_path, 'a').close()
        print(f"Neue dnsmasq Konfigurationsdatei erstellt: {main_config_path}")

    with open(main_config_path, 'r') as file:
        existing_lines = file.readlines()

    required_settings = [
        "domain-needed",
        "bogus-priv",
        "interface=lo",
        "bind-interfaces",
        "resolv-file=/run/resolv.conf",
        "no-poll",
        "no-hosts"
    ]

    for setting in required_settings:
        if all(setting not in line for line in existing_lines):
            existing_lines.append(setting + "\n")

    with open(main_config_path, 'w') as file:
        file.writelines(existing_lines)

    print("dnsmasq Konfiguration aktualisiert.")

def restart_dnsmasq():
    os.system("/etc/init.d/dnsmasq restart")

def configure_dnsmasq():
    backup_and_clear_dnsmasq_config()
    update_dnsmasq_config()
    restart_dnsmasq()

if __name__ == "__main__":
    configure_dnsmasq()
