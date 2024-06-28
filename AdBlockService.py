import asyncio
import aiofiles
import hashlib
import subprocess
import requests
import logging
import dbus
import dbus.service
from gi.repository import GLib
from vedbus import VeDbusService, VeDbusItemExport, VeDbusItemImport
from adblock_utils import get_network_settings, calculate_hash, convert_to_dnsmasq_format, download_adblock_list, save_combined_hosts, read_hosts_file, write_hosts_file

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
        self.local_file_path = '/etc/dnsmasq.d/adblock.conf'
        self.dnsmasq_config_path = "/etc/dnsmasq.conf"
        self.static_dnsmasq_config_path = "/etc/dnsmasq_static.conf"
        self.backup_dnsmasq_config_path = self.dnsmasq_config_path + ".bak"
        self.is_configuring = False
        self.is_downloading = False
        self.download_lock = asyncio.Lock()
        self.configure_lock = asyncio.Lock()

        self.network_settings = get_network_settings()

        if not os.path.exists(self.backup_dnsmasq_config_path):
            shutil.copy(self.dnsmasq_config_path, self.backup_dnsmasq_config_path)

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

    def start_download(self, path, value):
        if value:
            asyncio.create_task(self.update_adblock_list())
            self.dbus_service[path] = False

    def start_configure(self, path, value):
        if value:
            asyncio.create_task(self.configure_dnsmasq())
            self.dbus_service[path] = False

    async def update_adblock_list(self):
        async with self.download_lock:
            self.dbus_service['/Downloading'] = True
            adblock_list_urls = self.get_setting("/Settings/AdBlock/AdListURLs") or []
            last_known_hashes = self.get_setting("/Settings/AdBlock/LastKnownHashes") or {}

            all_lines = []
            for url in adblock_list_urls:
                content = await download_adblock_list(url)
                if content:
                    current_hash = calculate_hash(content)
                    if current_hash != last_known_hashes.get(url):
                        lines = content.splitlines()
                        all_lines.extend(lines)
                        last_known_hashes[url] = current_hash

            whitelist = self.get_setting("/Settings/AdBlock/Whitelist") or []
            blacklist = self.get_setting("/Settings/AdBlock/Blacklist") or []

            all_lines = list(set(all_lines) - set(whitelist)) + blacklist
            converted_list = convert_to_dnsmasq_format(all_lines)

            await save_combined_hosts(converted_list, self.local_file_path)

            self.set_setting("/Settings/AdBlock/LastKnownHashes", last_known_hashes)
            logger.info("AdBlock-Liste aktualisiert.")
            self.dbus_service['/Downloading'] = False

    async def configure_dnsmasq(self):
        async with self.configure_lock:
            self.dbus_service['/Configuring'] = True

            new_config = f"conf-file={self.static_dnsmasq_config_path}\n"
            if self.get_setting("/Settings/AdBlock/Enabled"):
                new_config += f"conf-file={self.local_file_path}\n"
            if self.get_setting("/Settings/AdBlock/DHCPEnabled"):
                dhcp_config = (
                    f"dhcp-range={self.network_settings['ip_range_start']},"
                    f"{self.network_settings['ip_range_end']},12h\n"
                    f"dhcp-option=option:router,{self.network_settings['default_gateway']}\n"
                    f"dhcp-option=option:dns-server,{self.network_settings['dns_server']}\n"
                )
                new_config += dhcp_config

            async with aiofiles.open(self.dnsmasq_config_path, 'w') as file:
                await file.write(new_config)
            await asyncio.to_thread(subprocess.run, ["/etc/init.d/dnsmasq", "restart"])
            logger.info("dnsmasq neu gestartet.")
            self.dbus_service['/Configuring'] = False

def main():
    bus = dbus.SystemBus()
    service = AdBlockService(bus)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
