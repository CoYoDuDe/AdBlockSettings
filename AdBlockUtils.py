import subprocess
import ipaddress
import logging
import requests
import aiofiles
import asyncio
import hashlib
from vedbus import VeDbusService, VeDbusItemExport, VeDbusItemImport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_network_settings():
    default_gateway = None
    dns_server = None
    ip_range_start = None
    ip_range_end = None

    try:
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if 'default' in line:
                parts = line.split()
                default_gateway = parts[2]
                break

        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        ip_address = None
        netmask = None
        for line in result.stdout.splitlines():
            if 'inet ' in line and 'broadcast' in line:
                parts = line.split()
                ip_address = parts[1]
                netmask = parts[3]
                break

        if ip_address and netmask:
            network = ipaddress.IPv4Network(f"{ip_address}/{netmask}", strict=False)
            ip_range_start = str(network.network_address + 100)
            ip_range_end = str(network.network_address + 200)
            dns_server = ip_address

        if dns_server is None:
            result = subprocess.run(['nmcli', 'dev', 'show'], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if 'IP4.DNS' in line:
                    dns_server = line.split()[-1]
                    break

    except Exception as e:
        logger.error(f"Fehler beim Ermitteln der Netzwerkeinstellungen: {e}")

    if default_gateway is None:
        default_gateway = "192.168.1.1"
    if dns_server is None:
        dns_server = "192.168.1.1"
    if ip_range_start is None:
        ip_range_start = "192.168.1.100"
    if ip_range_end is None:
        ip_range_end = "192.168.1.200"

    return ip_range_start, ip_range_end, default_gateway, dns_server

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

async def update_adblock_list(service):
    adblock_list_url = service.get_setting("/Settings/AdBlock/AdListURL")
    last_known_hash = service.get_setting("/Settings/AdBlock/LastKnownHash")

    try:
        response = await asyncio.to_thread(requests.get, adblock_list_url, timeout=10)
        response.raise_for_status()
        current_hash = calculate_hash(response.text)
        if current_hash != last_known_hash:
            converted_list = convert_to_dnsmasq_format(response.text.splitlines())
            async with aiofiles.open(service.local_file_path, 'w') as file:
                await file.write("\n".join(converted_list))
            service.set_setting("/Settings/AdBlock/LastKnownHash", current_hash)
            logger.info("AdBlock-Liste aktualisiert.")
        else:
            logger.info("Keine Änderungen in der AdBlock-Liste.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Herunterladen der AdBlock-Liste: {e}")

async def configure_dnsmasq(service):
    new_config = f"conf-file={service.static_dnsmasq_config_path}\n"

    if service.get_setting("/Settings/AdBlock/Enabled"):
        new_config += f"conf-file={service.local_file_path}\n"
    if service.get_setting("/Settings/AdBlock/DHCPEnabled"):
        dhcp_config = (
            f"dhcp-range={service.get_setting('/Settings/AdBlock/IPRangeStart')},"
            f"{service.get_setting('/Settings/AdBlock/IPRangeEnd')},12h\n"
            f"dhcp-option=option:router,{service.get_setting('/Settings/AdBlock/DefaultGateway')}\n"
            f"dhcp-option=option:dns-server,{service.get_setting('/Settings/AdBlock/DNSServer')}\n"
        )
        new_config += dhcp_config

    async with aiofiles.open(service.dnsmasq_config_path, 'w') as file:
        await file.write(new_config)
    await asyncio.to_thread(subprocess.run, ["/etc/init.d/dnsmasq", "restart"])
