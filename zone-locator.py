#!/usr/bin/env python3

import requests
import logging

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

DOMAIN = "example.com"
EMAIL = "email@mail.com"
API_KEY = "api_key"

headers = {
    "X-Auth-Email": EMAIL,
    "X-Auth-Key": API_KEY,
}

def make_request(url):
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.error(f'Failed to fetch {url}, status code: {response.status_code}')
        return None
    return response.json()["result"]

def get_zones():
    return make_request("https://api.cloudflare.com/client/v4/zones")

def get_dns_records(zone_id):
    return make_request(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records")

def main():
    zones = get_zones()
    for zone in zones:
        if zone["name"] == DOMAIN:
            logger.info(f"ZONE ID: {zone['id']}")
            records = get_dns_records(zone["id"])
            for record in records:
                logger.info(f"{record['type']} {record['name']} {record['id']}")
            break

if __name__ == "__main__":
    main()
