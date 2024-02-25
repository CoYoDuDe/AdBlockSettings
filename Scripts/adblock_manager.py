#!/usr/bin/env python3
import dbus

def get_dbus_setting(setting_path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object('com.victronenergy.settings', '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    return settings_interface.GetValue(setting_path)

def set_dbus_setting(setting_path, value):
    bus = dbus.SystemBus()
    settings_service = bus.get_object('com.victronenergy.settings', '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    settings_interface.SetValue(setting_path, value)

def manage_adblock_settings():
    enabled = get_dbus_setting('/Settings/AdBlock/Enabled')
    if enabled:
        ad_list_url = get_dbus_setting('/Settings/AdBlock/AdListURL')
        update_interval = get_dbus_setting('/Settings/AdBlock/UpdateInterval')
        update_time = get_dbus_setting('/Settings/AdBlock/UpdateTime')
        update_day = get_dbus_setting('/Settings/AdBlock/UpdateDay')
        dhcp_enabled = get_dbus_setting('/Settings/AdBlock/DHCPEnabled')
        ipv6_enabled = get_dbus_setting('/Settings/AdBlock/IPv6Enabled')
        
        print(f"AdBlock is enabled: {ad_list_url}, Update Interval: {update_interval}, Time: {update_time}, Day: {update_day}")
        print(f"DHCP Enabled: {dhcp_enabled}, IPv6 Enabled: {ipv6_enabled}")
        
        # Hier kommt Ihre Logik zum Aktualisieren der AdBlock-Liste und zur Konfiguration des Systems
        
    else:
        print("AdBlock is disabled.")

if __name__ == '__main__':
    manage_adblock_settings()
