import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import asyncio
import logging
from gi.repository import GLib
from adblock_utils import get_network_settings, update_adblock_list, configure_dnsmasq, VeDbusService, VeDbusItemExport, VeDbusItemImport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DBusGMainLoop(set_as_default=True)

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
        self.download_lock = asyncio.Lock()
        self.configure_lock = asyncio.Lock()

        self.initialize_settings()
        self.update_interval = self.get_setting("/Settings/AdBlock/UpdateInterval")
        self.adblock_enabled = self.get_setting("/Settings/AdBlock/Enabled")

    def initialize_settings(self):
        ip_range_start, ip_range_end, default_gateway, dns_server = get_network_settings()

        settings = {
            "/Settings/AdBlock/Enabled": 0,
            "/Settings/AdBlock/AdListURL": "https://example.com/adlist.txt",
            "/Settings/AdBlock/UpdateInterval": "weekly",
            "/Settings/AdBlock/DefaultGateway": default_gateway,
            "/Settings/AdBlock/DNSServer": dns_server,
            "/Settings/AdBlock/IPRangeStart": ip_range_start,
            "/Settings/AdBlock/IPRangeEnd": ip_range_end,
            "/Settings/AdBlock/DHCPEnabled": 0,
            "/Settings/AdBlock/IPv6Enabled": 0,
            "/Settings/AdBlock/LastKnownHash": ""
        }

        for path, default in settings.items():
            current_value = self.get_setting(path)
            if current_value is None or current_value == "":
                self.set_setting(path, default)

    def get_setting(self, path):
        try:
            item = VeDbusItemImport(self.bus, 'com.victronenergy.settings', path)
            value = item.get_value()
            if value is None:
                raise ValueError("Wert ist None")
            return value
        except Exception as e:
            logger.error(f"DBus Fehler bei {path}: {e}")
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
            async with self.download_lock:
                self.DownloadStarted()
                await update_adblock_list(self)
                self.DownloadFinished()
            self.dbus_service[path] = False

    async def start_configure(self, path, value):
        if value:
            async with self.configure_lock:
                self.ConfigureDnsmasqStarted()
                await update_adblock_list(self)
                await configure_dnsmasq(self)
                self.ConfigureDnsmasqFinished()
            self.dbus_service[path] = False

def main():
    bus = dbus.SystemBus()
    service = AdBlockService(bus)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
