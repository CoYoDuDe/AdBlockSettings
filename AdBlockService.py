#!/usr/bin/env python

import argparse
import requests
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import sys
import os
import hashlib
import shutil
import threading
from datetime import datetime, timedelta
from gi.repository import GLib
from pathlib import Path
import socket
import fcntl
import struct
import logging

# Pfad zu den benötigten Bibliotheken hinzufügen
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from vedbus import VeDbusService, VeDbusItemImport, VeDbusItemExport

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hilfsfunktionen
def log_info(message):
    logger.info(message)

def log_error(message):
    logger.error(message)

def get_default_gateway():
    try:
        with open('/proc/net/route') as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue
                return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    except Exception as e:
        log_error(f"Fehler beim Ermitteln des Standard-Gateways: {e}")
        return "192.168.1.1"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        interfaces = [i[1] for i in socket.if_nameindex()]
        for ifname in interfaces:
            try:
                ip_address = socket.inet_ntoa(fcntl.ioctl(
                    s.fileno(),
                    0x8915,
                    struct.pack('256s', ifname[:15].encode('utf-8'))
                )[20:24])
                if ip_address != "127.0.0.1":
                    return ip_address
            except IOError:
                continue
    except Exception as e:
        log_error(f"Fehler beim Ermitteln der lokalen IP-Adresse: {e}")
        return "192.168.1.1"

def get_network_settings():
    try:
        default_gateway = get_default_gateway()
        local_ip = get_local_ip()
        ip_range_start = default_gateway.rsplit('.', 1)[0] + ".100"
        ip_range_end = default_gateway.rsplit('.', 1)[0] + ".200"
        return {
            "default_gateway": default_gateway,
            "dns_server": local_ip,
            "ip_range_start": ip_range_start,
            "ip_range_end": ip_range_end
        }
    except Exception as e:
        log_error(f"Fehler beim Ermitteln der Netzwerkeinstellungen: {e}")
        return {
            "default_gateway": "192.168.1.1",
            "dns_server": "192.168.1.1",
            "ip_range_start": "192.168.1.100",
            "ip_range_end": "192.168.1.200"
        }

def calculate_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def convert_to_dnsmasq_format(lines):
    converted_lines = []
    for line in lines:
        if line.strip() and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                domain = parts[1]
                converted_line = f"address=/{domain}/#"
                converted_lines.append(converted_line)
    return converted_lines

DBusGMainLoop(set_as_default=True)

local_file_path = '/etc/dnsmasq.d/adblock.conf'
dnsmasq_config_path = "/etc/dnsmasq.conf"
static_dnsmasq_config_path = "/etc/dnsmasq_static.conf"
backup_dnsmasq_config_path = dnsmasq_config_path + ".bak"

class AdBlockService(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, '/AdBlockService')
        self.bus = bus
        self.dbus_service = VeDbusService('com.victronenergy.adblock', bus=self.bus)
        self.dbus_service.add_path('/DownloadTrigger', False, writeable=True, onchangecallback=self.start_download)
        self.dbus_service.add_path('/ConfigureTrigger', False, writeable=True, onchangecallback=self.start_configure)
        self.dbus_service.add_path('/Downloading', False, writeable=False)
        self.dbus_service.add_path('/Configuring', False, writeable=False)

        self.is_configuring = False
        self.is_downloading = False

        self.set_default_settings()

    def get_setting(self, path):
        try:
            item = VeDbusItemImport(self.bus, 'com.victronenergy.settings', path)
            return item.get_value()
        except Exception as e:
            log_error(f"DBus Fehler: {e}")
            return None

    def set_setting(self, path, value):
        try:
            item = VeDbusItemExport(self.bus, path, value, writeable=True)
            item.local_set_value(value)
            log_info(f"Wert für Pfad {path} im D-Bus aktualisiert: {value}")
        except Exception as e:
            log_error(f"Fehler beim Aktualisieren des D-Bus Wertes: {e}")

    def set_default_settings(self):
        network_settings = get_network_settings()
        settings = {
            "/Settings/AdBlock/BlocklistURLs": ["https://example.com/adlist.txt"],
            "/Settings/AdBlock/UpdateInterval": "weekly",
            "/Settings/AdBlock/DefaultGateway": network_settings["default_gateway"],
            "/Settings/AdBlock/DNSServer": network_settings["dns_server"],
            "/Settings/AdBlock/IPRangeStart": network_settings["ip_range_start"],
            "/Settings/AdBlock/IPRangeEnd": network_settings["ip_range_end"],
            "/Settings/AdBlock/DHCPEnabled": 0,
            "/Settings/AdBlock/IPv6Enabled": 0,
            "/Settings/AdBlock/LastKnownHash": "",
            "/Settings/AdBlock/Whitelist": [],
            "/Settings/AdBlock/Blacklist": []
        }

        for path, default in settings.items():
            current_value = self.get_setting(path)
            if current_value in [None, "", []]:
                self.set_setting(path, default)

    def DownloadStarted(self):
        self.is_downloading = True
        self.dbus_service['/Downloading'] = True

    def DownloadFinished(self):
        self.is_downloading = False
        self.dbus_service['/Downloading'] = False

    def ConfigureDnsmasqStarted(self):
        self.is_configuring = True
        self.dbus_service['/Configuring'] = True

    def ConfigureDnsmasqFinished(self):
        self.is_configuring = False
        self.dbus_service['/Configuring'] = False

    def start_download(self, path, value):
        if value:
            threading.Thread(target=self.update_adblock_list).start()
            self.dbus_service[path] = False

    def start_configure(self, path, value):
        if value:
            threading.Thread(target=self.update_adblock_list).start()
            while self.is_downloading:
                time.sleep(1)
            threading.Thread(target=self.configure_dnsmasq).start()
            self.dbus_service[path] = False

    def calculate_hash(self, content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def convert_to_dnsmasq_format(self, lines):
        converted_lines = []
        for line in lines:
            if line.strip() and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]
                    converted_line = f"address=/{domain}/#"
                    converted_lines.append(converted_line)
        return converted_lines

    def update_adblock_list(self):
        if not self.is_downloading:
            self.DownloadStarted()
            adblock_list_urls = self.get_setting("/Settings/AdBlock/BlocklistURLs")
            whitelist_urls = self.get_setting("/Settings/AdBlock/Whitelist")
            blacklist_urls = self.get_setting("/Settings/AdBlock/Blacklist")
            last_known_hash = self.get_setting("/Settings/AdBlock/LastKnownHash")

            combined_content = ""
            for url in adblock_list_urls:
                try:
                    response = requests.get(url.strip(), timeout=10)
                    response.raise_for_status()
                    combined_content += response.text + "\n"
                except requests.exceptions.RequestException as e:
                    log_error(f"Fehler beim Herunterladen von {url}: {e}")

            current_hash = self.calculate_hash(combined_content)
            if current_hash != last_known_hash:
                converted_list = self.convert_to_dnsmasq_format(combined_content.splitlines())

                whitelist_entries = [f"address=/{url}/" for url in whitelist_urls]
                blacklist_entries = [f"address=/{url}/#" for url in blacklist_urls]
                converted_list.extend(whitelist_entries)
                converted_list.extend(blacklist_entries)

                with open(local_file_path, 'w') as file:
                    file.write("\n".join(converted_list))
                self.set_setting("/Settings/AdBlock/LastKnownHash", current_hash)
                log_info("AdBlock-Liste aktualisiert.")
            else:
                log_info("Keine Änderungen in der AdBlock-Liste.")
            self.DownloadFinished()

    def configure_dnsmasq(self):
        if not self.is_configuring:
            self.ConfigureDnsmasqStarted()
            new_config = f"conf-file={static_dnsmasq_config_path}\n"

            if self.get_setting("/Settings/AdBlock/Enabled"):
                new_config += f"conf-file={local_file_path}\n"
            if self.get_setting("/Settings/AdBlock/DHCPEnabled"):
                dhcp_config = (
                    f"dhcp-range={self.get_setting('/Settings/AdBlock/IPRangeStart')},"
                    f"{self.get_setting('/Settings/AdBlock/IPRangeEnd')},12h\n"
                    f"dhcp-option=option:router,{self.get_setting('/Settings/AdBlock/DefaultGateway')}\n"
                    f"dhcp-option=option:dns-server,{self.get_setting('/Settings/AdBlock/DNSServer')}\n"
                )
                new_config += dhcp_config
            if self.get_setting("/Settings/AdBlock/IPv6Enabled"):
                new_config += "enable-ra\n"

            with open(dnsmasq_config_path, 'w') as file:
                file.write(new_config)
            self.restart_dnsmasq()
            self.ConfigureDnsmasqFinished()

    def restart_dnsmasq(self):
        os.system("/etc/init.d/dnsmasq restart")
        log_info("dnsmasq neu gestartet.")

    def schedule_next_update(self):
        update_interval = self.get_setting("/Settings/AdBlock/UpdateInterval")
        self.next_update = datetime.now()
        if update_interval == "daily":
            self.next_update += timedelta(days=1)
        elif update_interval == "weekly":
            self.next_update += timedelta(weeks=1)
        elif update_interval == "monthly":
            self.next_update += timedelta(days=30)
        log_info(f"Nächstes Update geplant für {self.next_update}")

    def check_for_updates(self):
        if datetime.now() >= self.next_update and self.get_setting("/Settings/AdBlock/Enabled"):
            self.update_adblock_list()
            self.schedule_next_update()
        threading.Timer(86400, self.check_for_updates).start()

def main():
    bus = dbus.SystemBus()
    service = AdBlockService(bus)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
