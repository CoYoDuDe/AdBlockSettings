#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import os

def get_dbus_setting_value(path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object("com.victronenergy.settings", path)
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.BusItem')
    return settings_interface.GetValue()

def backup_and_clear_dnsmasq_config(main_config_path="/etc/dnsmasq.conf"):
    backup_config_path = f"{main_config_path}.orig"
    if not os.path.exists(backup_config_path):
        os.rename(main_config_path, backup_config_path)
        print(f"Original dnsmasq Konfiguration gesichert als {backup_config_path}")

def update_dnsmasq_config(main_config_path="/etc/dnsmasq.conf", adlist_config_path="/etc/dnsmasq.d/AdList.conf"):
    adblock_enabled = get_dbus_setting_value("/Settings/AdBlock/Enabled")[0]
    dhcp_enabled = get_dbus_setting_value("/Settings/AdBlock/DHCPEnabled")[0]
    ipv6_enabled = get_dbus_setting_value("/Settings/AdBlock/IPv6Enabled")[0]

    with open(main_config_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    dhcp_configured = False
    ipv6_configured = False
    adblock_configured = False

    for line in lines:
        if "dhcp-range" in line or "dhcp-option" in line or "dhcp-authoritative" in line:
            dhcp_configured = True
            if not dhcp_enabled:
                if not line.strip().startswith("#"):
                    line = "#" + line
            else:
                if line.strip().startswith("#"):
                    line = line[1:]
        elif "enable-ra" in line:
            ipv6_configured = True
            if not ipv6_enabled:
                if not line.strip().startswith("#"):
                    line = "#" + line
            else:
                if line.strip().startswith("#"):
                    line = line[1:]
        elif adlist_config_path in line:
            adblock_configured = True
            if not adblock_enabled:
                continue
        updated_lines.append(line)

    if adblock_enabled and not adblock_configured:
        updated_lines.append(f"conf-file={adlist_config_path}\n")

    with open(main_config_path, 'w') as file:
        file.writelines(updated_lines)

    print("dnsmasq Konfiguration aktualisiert.")

def restart_dnsmasq():
    os.system("service dnsmasq restart")

def configure_dnsmasq():
    backup_and_clear_dnsmasq_config()
    update_dnsmasq_config()
    restart_dnsmasq()

if __name__ == "__main__":
    configure_dnsmasq()
