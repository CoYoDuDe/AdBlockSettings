#!/usr/bin/env python

import argparse
import requests
from pathlib import Path
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import sys
import os
import hashlib
import subprocess
import time
from datetime import datetime, timedelta
import threading
import logging
import shutil
import asyncio
from gi.repository import GLib

sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from vedbus import VeDbusService, VeDbusItemExport, VeDbusItemImport

DBusGMainLoop(set_as_default=True)

local_file_path = '/etc/dnsmasq.d/adblock.conf'
dnsmasq_config_path = "/etc/dnsmasq.conf"
static_dnsmasq_config_path = "/etc/dnsmasq_static.conf"
backup_dnsmasq_config_path = dnsmasq_config_path + ".bak"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    def get_setting(self, path):
        try:
            item = VeDbusItemImport(self.bus, 'com.victronenergy.settings', path)
            return item.get_value()
        except Exception as e:
            logger.error(f"DBus Fehler: {e}")
            return None

    def set_setting(self, path, value):
        try:
            item = VeDbusItemExport(self.bus, path, value, writeable=True)
            item.local_set_value(value)
            logger.info(f"Wert für Pfad {path} im D-Bus aktualisiert: {value}")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des D-Bus Wertes: {e}")

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

    async def start_download(self, path, value):
        if value:
            asyncio.create_task(self.update_adblock_list())
            self.dbus_service[path] = False

    async def start_configure(self, path, value):
        if value:
            await self.update_adblock_list()
            await self.configure_dnsmasq()
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

    async def update_adblock_list(self):
        if not self.is_downloading:
            with self.download_lock:
                self.DownloadStarted()
                adblock_list_url = self.get_setting("/Settings/AdBlock/AdListURL")
                last_known_hash = self.get_setting("/Settings/AdBlock/LastKnownHash")

                try:
                    response = await asyncio.to_thread(requests.get, adblock_list_url, timeout=10)
                    response.raise_for_status()
                    current_hash = self.calculate_hash(response.text)
                    if current_hash != last_known_hash:
                        converted_list = self.convert_to_dnsmasq_format(response.text.splitlines())
                        async with aiofiles.open(local_file_path, 'w') as file:
                            await file.write("\n".join(converted_list))
                        self.set_setting("/Settings/AdBlock/LastKnownHash", current_hash)
                        logger.info("AdBlock-Liste aktualisiert.")
                    else:
                        logger.info("Keine Änderungen in der AdBlock-Liste.")
                except requests.exceptions.HTTPError as http_err:
                    logger.error(f"HTTP Fehler: {http_err}")
                except requests.exceptions.ConnectionError as conn_err:
                    logger.error(f"Verbindungsfehler: {conn_err}")
                except requests.exceptions.Timeout as timeout_err:
                    logger.error(f"Timeout Fehler: {timeout_err}")
                except requests.exceptions.RequestException as req_err:
                    logger.error(f"Allgemeiner Fehler: {req_err}")
                finally:
                    self.DownloadFinished()

    async def configure_dnsmasq(self):
        if not self.is_configuring:
            with self.configure_lock:
                self.ConfigureDnsmasqStarted()
                new_config = f"conf-file={static_dnsmasq_config_path}\n"

                if self.get_setting("/Settings/AdBlock/Enabled"):
                    new_config += f"conf-file={local_file_path}\n"
                if self.get_setting("/Settings/AdBlock/DHCPEnabled"):
                    dhcp_config = f"dhcp-range={self.get_setting('/Settings/AdBlock/IPRangeStart')},{self.get_setting('/Settings/AdBlock/IPRangeEnd')},12h\n"
                    dhcp_config += f"dhcp-option=option:router,{self.get_setting('/Settings/AdBlock/DefaultGateway')}\n"
                    dhcp_config += f"dhcp-option=option:dns-server,{self.get_setting('/Settings/AdBlock/DNSServer')}\n"
                    new_config += dhcp_config
                if self.get_setting("/Settings/AdBlock/IPv6Enabled"):
                    new_config += "enable-ra\n"

                async with aiofiles.open(dnsmasq_config_path, 'w') as file:
                    await file.write(new_config)
                await asyncio.to_thread(self.restart_dnsmasq)
                self.ConfigureDnsmasqFinished()

    def restart_dnsmasq(self):
        os.system("/etc/init.d/dnsmasq restart")
        logger.info("dnsmasq neu gestartet.")

    def schedule_next_update(self):
        if self.update_interval == "daily":
            self.next_update += timedelta(days=1)
        elif self.update_interval == "weekly":
            self.next_update += timedelta(days=7)
        elif self.update_interval == "monthly":
            self.next_update += timedelta(days=30)
        logger.info(f"Nächstes Update geplant für {self.next_update}")

    def check_for_updates(self):
        if datetime.now() >= self.next_update and self.adblock_enabled:
            asyncio.run(self.update_adblock_list())
            self.schedule_next_update()

        interval = 86400
        threading.Timer(interval, self.check_for_updates).start()

def main():
    bus = dbus.SystemBus()
    service = AdBlockService(bus)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
