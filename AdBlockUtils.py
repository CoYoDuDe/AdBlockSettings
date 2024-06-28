import os
import hashlib
import requests
import aiofiles
from adblock_utils import get_network_settings, calculate_hash, convert_to_dnsmasq_format

def get_network_settings():
    try:
        # Bestimmen Sie das Standard-Gateway
        with os.popen("ip route | grep default | awk '{print $3}'") as stream:
            default_gateway = stream.read().strip()

        # Bestimmen Sie den DNS-Server
        with os.popen("grep 'nameserver' /etc/resolv.conf | awk '{print $2}'") as stream:
            dns_server = stream.read().strip()

        # Bestimmen Sie die IP-Range (Beispiel für eine typische lokale Netzwerk-Konfiguration)
        ip_range_start = default_gateway[:-1] + "100"  # Annahme: 192.168.1.1 -> 192.168.1.100
        ip_range_end = default_gateway[:-1] + "200"  # Annahme: 192.168.1.1 -> 192.168.1.200

        return {
            "default_gateway": default_gateway or "192.168.1.1",
            "dns_server": dns_server or default_gateway or "192.168.1.1",
            "ip_range_start": ip_range_start,
            "ip_range_end": ip_range_end
        }
    except Exception as e:
        # Falls ein Fehler auftritt, verwenden Sie Standardwerte
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

async def download_adblock_list(url):
    try:
        response = await asyncio.to_thread(requests.get, url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Herunterladen der AdBlock-Liste von {url}: {e}")
        return None

async def save_combined_hosts(lines, path):
    async with aiofiles.open(path, 'w') as file:
        await file.write("\n".join(lines))

async def read_hosts_file(path):
    if os.path.exists(path):
        async with aiofiles.open(path, 'r') as file:
            return await file.readlines()
    return []

async def write_hosts_file(path, lines):
    async with aiofiles.open(path, 'w') as file:
        await file.writelines(lines)
