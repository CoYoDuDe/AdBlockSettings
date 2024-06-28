import os
import hashlib
import requests
import aiofiles
import subprocess
import netifaces
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_info(message):
    logger.info(message)

def log_error(message):
    logger.error(message)

def get_default_gateway():
    try:
        gateways = netifaces.gateways()
        default_gateway = gateways['default'][netifaces.AF_INET][0]
        return default_gateway
    except Exception as e:
        log_error(f"Fehler beim Ermitteln des Standard-Gateways: {e}")
        return "192.168.1.1"

def get_local_ip():
    try:
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            addresses = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addresses:
                ipv4_info = addresses[netifaces.AF_INET][0]
                ip_address = ipv4_info['addr']
                return ip_address
    except Exception as e:
        log_error(f"Fehler beim Ermitteln der lokalen IP-Adresse: {e}")
        return "192.168.1.1"

def restart_service(service_name):
    try:
        subprocess.run(["systemctl", "restart", service_name], check=True)
        log_info(f"Service {service_name} wurde erfolgreich neu gestartet.")
    except subprocess.CalledProcessError as e:
        log_error(f"Fehler beim Neustarten des Service {service_name}: {e}")

def get_network_settings():
    try:
        default_gateway = get_default_gateway()
        local_ip = get_local_ip()
        ip_range_start = default_gateway[:-1] + "100"
        ip_range_end = default_gateway[:-1] + "200"
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

async def download_adblock_list(url):
    try:
        response = await asyncio.to_thread(requests.get, url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        log_error(f"Fehler beim Herunterladen der AdBlock-Liste von {url}: {e}")
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
