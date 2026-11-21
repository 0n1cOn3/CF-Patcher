#!/usr/bin/env python3
"""List zone + DNS record ids for a domain. No secrets in source — env only.

Usage:
  CF_API_TOKEN=xxx DOMAIN=example.com python3 zone-locator.py
  (or CF_API_EMAIL + CF_API_KEY for Global API Key auth)
"""
import os
import sys

import requests

DOMAIN = os.environ.get("DOMAIN", "example.com")
token = os.environ.get("CF_API_TOKEN")
headers = ({"Authorization": f"Bearer {token}"} if token else {
    "X-Auth-Email": os.environ["CF_API_EMAIL"],
    "X-Auth-Key": os.environ["CF_API_KEY"]})
base = "https://api.cloudflare.com/client/v4"


def get(path):
    r = requests.get(f"{base}{path}", headers=headers, timeout=30)
    body = r.json()
    if not body.get("success"):
        sys.exit(f"CF API error: {body.get('errors')}")
    return body["result"]


for zone in get(f"/zones?name={DOMAIN}"):
    print("ZONE ID:", zone["id"])
    for rec in get(f"/zones/{zone['id']}/dns_records?per_page=100"):
        print(f"  {rec['type']:6} {rec['name']:40} {rec['id']}  "
              f"proxied={rec['proxied']}")
    break
else:
    sys.exit(f"zone not found: {DOMAIN}")
