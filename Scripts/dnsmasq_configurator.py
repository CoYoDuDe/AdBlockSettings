import dbus
import os

def get_dbus_setting(service, path):
    bus = dbus.SystemBus()
    settings_service = bus.get_object(service, '/')
    settings_interface = dbus.Interface(settings_service, dbus_interface='org.freedesktop.DBus.Properties')
    return settings_interface.Get('com.victronenergy.settings', path)

def backup_and_clear_dnsmasq_config(main_config_path="/etc/dnsmasq.conf"):
    backup_config_path = f"{main_config_path}.orig"
    if not os.path.exists(backup_config_path):
        os.rename(main_config_path, backup_config_path)
        print(f"Original dnsmasq Konfiguration gesichert als {backup_config_path}")

def update_dnsmasq_config(main_config_path="/etc/dnsmasq.conf", adlist_config_path="/etc/dnsmasq.d/AdList.conf"):
    adblock_enabled = get_dbus_setting("com.victronenergy.settings", "/Settings/AdBlock/Enabled")
    dhcp_enabled = get_dbus_setting("com.victronenergy.settings", "/Settings/AdBlock/DHCPEnabled")
    ipv6_enabled = get_dbus_setting("com.victronenergy.settings", "/Settings/AdBlock/IPv6Enabled")

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
                continue  # Ãœberspringe das HinzufÃ¼gen dieser Zeile, wenn AdBlock deaktiviert ist
        updated_lines.append(line)

    if adblock_enabled and not adblock_configured:
        updated_lines.append(f"conf-file={adlist_config_path}\n")

    with open(main_config_path, 'w') as file:
        file.writelines(updated_lines)

    print("dnsmasq Konfiguration aktualisiert.")

def restart_dnsmasq():
    os.system("/etc/init.d/dnsmasq restart")
    print("dnsmasq neu gestartet.")

if __name__ == "__main__":
    main_config_path = "/etc/dnsmasq.conf"
    adlist_config_path = "/etc/dnsmasq.d/AdList.conf"
    backup_and_clear_dnsmasq_config(main_config_path)
    update_dnsmasq_config(main_config_path, adlist_config_path)
    restart_dnsmasq()
