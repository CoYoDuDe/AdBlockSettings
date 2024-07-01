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
import time

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
        self.download_lock = threading.Lock()
        self.configure_lock = threading.Lock()

        self.next_update = datetime.now()
        self.update_interval = self.get_setting("/Settings/AdBlock/UpdateInterval")
        self.adblock_enabled = self.get_setting("/Settings/AdBlock/Enabled")

        if not os.path.exists(backup_dnsmasq_config_path):
            shutil.copy(dnsmasq_config_path, backup_dnsmasq_config_path)

        self.ensure_array_paths()
        self.set_default_settings()

    def get_setting(self, path):
        try:
            item = VeDbusItemImport(self.bus, 'com.victronenergy.settings', path)
            value = item.get_value()
            log_info(f"Aktueller Wert für Pfad {path}: {value}")
            return value
        except Exception as e:
            log_error(f"DBus Fehler beim Abrufen des Wertes für Pfad {path}: {e}")
            return None

    def set_setting(self, path, value):
        try:
            if isinstance(value, list):
                value = dbus.Array(value, signature='s')
            item = VeDbusItemImport(self.bus, 'com.victronenergy.settings', path)
            item.set_value(value)
            time.sleep(0.5)  # Wartezeit erhöhen, um sicherzustellen, dass der Wert gesetzt wird
            new_value = self.get_setting(path)
            if new_value != value:
                log_error(f"Fehler beim Setzen des Standardwerts für Pfad {path}. Erwartet: {value}, Aktuell: {new_value}")
            else:
                log_info(f"Wert für Pfad {path} im D-Bus erfolgreich aktualisiert: {value}")
        except Exception as e:
            log_error(f"Fehler beim Aktualisieren des D-Bus Wertes für Pfad {path}: {e}")

    def ensure_array_paths(self):
        array_paths = [
            "/Settings/AdBlock/BlocklistURLs",
            "/Settings/AdBlock/Whitelist",
            "/Settings/AdBlock/Blacklist"
        ]
        for path in array_paths:
            value = self.get_setting(path)
            if value is None:
                try:
                    self.dbus_service.add_path(path, dbus.Array([], signature='s'), writeable=True)
                    log_info(f"Pfad {path} wurde im D-Bus angelegt")
                except Exception as e:
                    log_error(f"Fehler beim Anlegen des Pfads {path}: {e}")

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
            if current_value is None or current_value == "" or current_value == []:
                log_info(f"Setze Standardwert für Pfad {path}: {default}")
                self.set_setting(path, default)
            else:
                log_info(f"Behalte aktuellen Wert für Pfad {path}: {current_value}")

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

    def update_adblock_list(self):
        if not self.is_downloading:
            with self.download_lock:
                self.DownloadStarted()
                adblock_list_urls = self.get_setting("/Settings/AdBlock/BlocklistURLs")
                whitelist_urls = self.get_setting("/Settings/AdBlock/Whitelist")
                blacklist_urls = self.get_setting("/Settings/AdBlock/Blacklist")
                last_known_hash = self.get_setting("/Settings/AdBlock/LastKnownHash")

                if adblock_list_urls is None:
                    log_error("AdBlock-Liste ist leer. Abbruch.")
                    self.DownloadFinished()
                    return

                combined_content = ""
                for url in adblock_list_urls:
                    try:
                        response = requests.get(url.strip(), timeout=10)
                        response.raise_for_status()
                        combined_content += response.text + "\n"
                    except requests.exceptions.RequestException as e:
                        log_error(f"Fehler beim Herunterladen von {url}: {e}")

                current_hash = calculate_hash(combined_content)
                if current_hash != last_known_hash:
                    converted_list = convert_to_dnsmasq_format(combined_content.splitlines())

                    whitelist_entries = [f"address=/{url}/" for url in (whitelist_urls or [])]
                    blacklist_entries = [f"address=/{url}/#" for url in (blacklist_urls or [])]
                    converted_list.extend(whitelist_entries)
                    converted_list.extend(blacklist_entries)

                    with open('/etc/dnsmasq.d/adblock.conf', 'w') as f:
                        f.write('\n'.join(converted_list))

                    self.set_setting("/Settings/AdBlock/LastKnownHash", current_hash)
                self.DownloadFinished()
        else:
            log_info("Download is already in progress.")

    def configure_dnsmasq(self):
        if not self.is_configuring:
            with self.configure_lock:
                self.ConfigureDnsmasqStarted()
                try:
                    if os.path.exists(static_dnsmasq_config_path):
                        shutil.copy(static_dnsmasq_config_path, dnsmasq_config_path)
                    else:
                        shutil.copy(backup_dnsmasq_config_path, dnsmasq_config_path)

                    with open(dnsmasq_config_path, 'a') as f:
                        f.write(f"\nconf-file={local_file_path}\n")

                    os.system('systemctl restart dnsmasq')
                    self.ConfigureDnsmasqFinished()
                except Exception as e:
                    log_error(f"Fehler beim Konfigurieren von dnsmasq: {e}")
                    self.ConfigureDnsmasqFinished()
        else:
            log_info("Configuration is already in progress.")

def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adblock_service = AdBlockService(bus)

    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
