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

from gi.repository import GLib

sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from vedbus import VeDbusService, VeDbusItemExport, VeDbusItemImport

DBusGMainLoop(set_as_default=True)

local_file_path = '/etc/dnsmasq.d/adblock.conf'
dnsmasq_config_path = "/etc/dnsmasq.conf"
static_dnsmasq_config_path = "/etc/dnsmasq_static.conf"

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

        # Überprüfung bei jedem Start
        self.check_gui_and_patch()

    def get_setting(self, path):
        try:
            item = VeDbusItemImport(self.bus, 'com.victronenergy.settings', path)
            return item.get_value()
        except Exception as e:
            print(f"DBus Fehler: {e}")
            return None

    def set_setting(self, path, value):
        try:
            item = VeDbusItemExport(self.bus, path, value, writeable=True)
            item.local_set_value(value)
            print(f"Wert für Pfad {path} im D-Bus aktualisiert: {value}")
        except Exception as e:
            print(f"Fehler beim Aktualisieren des D-Bus Wertes: {e}")

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
            adblock_list_url = self.get_setting("/Settings/AdBlock/AdListURL")
            last_known_hash = self.get_setting("/Settings/AdBlock/LastKnownHash")

            try:
                response = requests.get(adblock_list_url, timeout=10)
                if response.status_code == 200:
                    current_hash = self.calculate_hash(response.text)
                    if current_hash != last_known_hash:
                        converted_list = self.convert_to_dnsmasq_format(response.text.splitlines())
                        with open(local_file_path, 'w') as file:
                            file.write("\n".join(converted_list))
                        self.set_setting("/Settings/AdBlock/LastKnownHash", current_hash)
                        print("AdBlock-Liste aktualisiert.")
                    else:
                        print("Keine Änderungen in der AdBlock-Liste.")
                else:
                    print(f"Fehler beim Download: HTTP {response.status_code}")
            except requests.RequestException as e:
                print(f"Download fehlgeschlagen: {e}")
            finally:
                self.DownloadFinished()

    def configure_dnsmasq(self):
        if not self.is_configuring:
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

            with open(dnsmasq_config_path, 'w') as file:
                file.write(new_config)
            self.restart_dnsmasq()
            self.ConfigureDnsmasqFinished()

    def restart_dnsmasq(self):
        os.system("/etc/init.d/dnsmasq restart")
        print("dnsmasq neu gestartet.")

    def schedule_next_update(self):
        if self.update_interval == "daily":
            self.next_update += timedelta(days=1)
        elif self.update_interval == "weekly":
            self.next_update += timedelta(days=7)
        elif self.update_interval == "monthly":
            self.next_update += timedelta(days=30)
        print(f"Nächstes Update geplant für {self.next_update}")

    def check_for_updates(self):
        if datetime.now() >= self.next_update and self.adblock_enabled:
            self.update_adblock_list()
            self.schedule_next_update()

        interval = 86400
        threading.Timer(interval, self.check_for_updates).start()

    def check_gui_and_patch(self):
        qml_path = "/opt/victronenergy/gui/qml/PageSettingsAdBlock.qml"
        patch_path = "/opt/victronenergy/gui/qml/PageSettings.qml"
        patch_source = "/data/AdBlockSettings/FileSets/PatchSource/PageSettings.qml.patch"

        if not os.path.exists(qml_path) or not self.is_patch_applied(patch_path, patch_source):
            print("GUI-Dateien oder Patch fehlen. Führe Installation durch.")
            subprocess.run(["/data/AdBlockSettings/setup.sh", "CHECK"])

    def is_patch_applied(self, patch_path, patch_source):
        result = subprocess.run(["patch", "--dry-run", "--silent", "-f", "-R", patch_path, "-i", patch_source], capture_output=True)
        return result.returncode == 0

def main():
    bus = dbus.SystemBus()
    service = AdBlockService(bus)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
