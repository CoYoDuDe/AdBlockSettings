import dbus
import os

def get_dbus_setting(service, path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object(service, '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='com.victronenergy.Settings')
    return settings_interface.GetValue(path)

def configure_dnsmasq(adblock_conf_path):
    # Einstellungen aus D-Bus auslesen
    adblock_service = "com.victronenergy.settings"
    enable_dhcp = get_dbus_setting(adblock_service, "/Settings/AdBlock/DHCPEnabled") == 1
    dhcp_range_start = get_dbus_setting(adblock_service, "/Settings/AdBlock/IPRangeStart")
    dhcp_range_end = get_dbus_setting(adblock_service, "/Settings/AdBlock/IPRangeEnd")
    enable_adblock = get_dbus_setting(adblock_service, "/Settings/AdBlock/Enabled") == 1
    enable_ipv6 = get_dbus_setting(adblock_service, "/Settings/AdBlock/IPv6Enabled") == 1

    # Adblock-Konfiguration schreiben
    if enable_adblock:
        with open(adblock_conf_path, 'w') as conf_file:
            conf_file.write("# Adblock-Konfiguration\n")
            conf_file.write("conf-file=/etc/dnsmasq.d/adblock_list.conf\n")
    
    # DHCP-Konfiguration schreiben, falls aktiviert
    if enable_dhcp:
        with open('/etc/dnsmasq.d/dhcp.conf', 'w') as dhcp_conf:
            dhcp_conf.write("# DHCP-Konfiguration\n")
            dhcp_conf.write(f"dhcp-range={dhcp_range_start},{dhcp_range_end},24h\n")

    # IPv6-Konfiguration schreiben, falls aktiviert
    if enable_ipv6:
        with open('/etc/dnsmasq.d/ipv6.conf', 'w') as ipv6_conf:
            ipv6_conf.write("# IPv6-Konfiguration\n")
            ipv6_conf.write("enable-ra\n")
            ipv6_conf.write("dhcp-range=::1,constructor:eth0,ra-stateless,ra-names\n")

    # dnsmasq neu starten, um die Änderungen zu übernehmen
    os.system('systemctl restart dnsmasq')

# Konfigurationspfad für Adblock
adblock_conf_path = '/etc/dnsmasq.d/adblock.conf'

# dnsmasq mit den aktuellen Einstellungen konfigurieren
configure_dnsmasq(adblock_conf_path)
