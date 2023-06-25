#!/usr/bin/env python3

import CloudFlare
import json
import requests
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Load configuration file
with open("config.json") as f:
    config = json.load(f)

# Function to query public IP address
def get_public_ip(attempts=3):
    endpoint = "https://ipinfo.io/json"

    for _ in range(attempts):
        response = requests.get(endpoint, verify=True)

        if response.status_code == 200:
            return response.json().get("ip")

        time.sleep(1)

    logger.error(f"Failed to get public IP after {attempts} attempts.")
    return None

class CloudflarePatcher:
    def __init__(self, account) -> None:
        self.cf = CloudFlare.CloudFlare(account["email"], account["api_key"])
        self.account = account
        self.zone_id = account["zone_id"]

    def load_variables(self):
        variables = {
            variable: globals()[f"get_{variable}"]()
            for variable in self.account["variables"]
        }

        logger.info(f"New Variables: {variables}")
        return variables

    def parse_record(self, record):
        record_str = json.dumps(record)
        variables = self.load_variables()
        for variable in variables:
            record_str = record_str.replace("{{" + variable + "}}", variables[variable])
        return json.loads(record_str)

    def patch_dns_records(self):
        for dns_record in self.account["dns_records"]:
            record = self.parse_record(dns_record["value"])
            try:
                self.cf.zones.dns_records.patch(
                    self.zone_id, dns_record["id"], data=record
                )
                dns_record["value"] = record
                logger.info(f"Updated {dns_record}")
            except Exception as e:
                logger.error(f"Error in /zones.dns_records.patch {dns_record} - {e}")

def main():
    last_ip = None
    while True:
        curr_ip = get_public_ip()
        if curr_ip != last_ip:
            for account in config:
                patcher = CloudflarePatcher(account)
                patcher.patch_dns_records()
            last_ip = curr_ip
        logger.info("Sleeping for 15 minutes")
        time.sleep(60 * 15)


if __name__ == "__main__":
    main()
