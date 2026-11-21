#!/usr/bin/env python3
"""CF-Patcher — Cloudflare DynDNS updater.

Auth (pick one):
  CF_API_TOKEN              — recommended, scoped API token (Zone:DNS:Edit)
  CF_API_EMAIL + CF_API_KEY — fallback, Global API Key

Config via config.json (see config.example.json) or CF_PATCHER_CONFIG env
pointing to another JSON file. Secrets NEVER go into the JSON — env only.
"""

import json
import os
import sys
import time

import requests

IP_ENDPOINTS = [
    "https://cloudflare.com/cdn-cgi/trace",  # ip=1.2.3.4 line
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
]
IP_TIMEOUT = 10
CHECK_INTERVAL = int(os.environ.get("CF_CHECK_INTERVAL", "300"))  # seconds
RETRY_BACKOFF = (10, 60, 300, 900)


def log(msg):
    print(msg, flush=True)


def auth_headers(cfg):
    token = os.environ.get("CF_API_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    email = os.environ.get("CF_API_EMAIL")
    key = os.environ.get("CF_API_KEY")
    if email and key:
        return {"X-Auth-Email": email, "X-Auth-Key": key}
    sys.exit("No auth: set CF_API_TOKEN or CF_API_EMAIL+CF_API_KEY")


def get_public_ip():
    """Query multiple endpoints, return the first consensus answer."""
    answers = {}
    for url in IP_ENDPOINTS:
        try:
            r = requests.get(url, timeout=IP_TIMEOUT)
            r.raise_for_status()
            ip = (r.text.split("ip=")[1].split()[0] if "ip=" in r.text
                  else r.text.strip())
            if ip:
                answers[ip] = answers.get(ip, 0) + 1
        except Exception as e:
            log(f"IP endpoint {url} failed: {e}")
    if not answers:
        raise RuntimeError("all IP endpoints failed")
    # majority vote; on tie, any answer is better than none
    return max(answers, key=answers.get)


def cf_request(method, path, headers, data=None):
    r = requests.request(method, f"https://api.cloudflare.com/client/v4{path}",
                         headers=headers, json=data, timeout=30)
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"CF API {path}: {body.get('errors')}")
    return body["result"]


def find_zone_id(headers, domain):
    zones = cf_request("GET", f"/zones?name={domain}", headers)
    if not zones:
        raise RuntimeError(f"zone not found: {domain}")
    return zones[0]["id"]


def find_record(headers, zone_id, name):
    recs = cf_request("GET", f"/zones/{zone_id}/dns_records?name={name}",
                      headers)
    if not recs:
        raise RuntimeError(f"record not found: {name}")
    return recs[0]


def resolve_records(headers, account):
    """Zone/records by name (preferred) or explicit ids (legacy config)."""
    zone_id = account.get("zone_id")
    if not zone_id:
        zone_id = find_zone_id(headers, account["domain"])
    out = []
    for rec in account["dns_records"]:
        r = dict(rec["value"])
        if rec.get("name") and not rec.get("id"):
            found = find_record(headers, zone_id, rec["name"])
            rec = dict(rec, id=found["id"])
            r.setdefault("type", found["type"])
            r.setdefault("name", found["name"])
            r.setdefault("ttl", found["ttl"])
            r.setdefault("proxied", found["proxied"])
        r.setdefault("ttl", 60)
        out.append((rec["id"], r, r.get("name", rec.get("id"))))
    return zone_id, out


def substitute(record, variables):
    for key, val in variables.items():
        record = {k: (v.replace("{{" + key + "}}", val) if isinstance(v, str)
                      else v) for k, v in record.items()}
    return record


def patch_dns_records(headers, account):
    zone_id, records = resolve_records(headers, account)
    for rec_id, value, name in records:
        value = substitute(value, {"public_ip": _current_ip})
        try:
            cf_request("PATCH", f"/zones/{zone_id}/dns_records/{rec_id}",
                       headers, value)
            log(f"updated {name} -> {value.get('content')}")
        except Exception as e:
            log(f"ERROR updating {name}: {e} (continuing)")


_current_ip = None


def run(headers, config):
    global _current_ip
    _current_ip = get_public_ip()
    log(f"current public IP: {_current_ip}")
    for account in config:
        patch_dns_records(headers, account)


def main():
    cfg_path = os.environ.get("CF_PATCHER_CONFIG", "config.json")
    config = json.load(open(cfg_path))
    headers = auth_headers(config)
    last_ip = None
    fail_count = 0
    while True:
        try:
            ip = get_public_ip()
            if ip != last_ip:
                run(headers, config)
                last_ip = ip
                fail_count = 0
            else:
                log("IP unchanged, nothing to do")
        except Exception as e:
            fail_count += 1
            wait = RETRY_BACKOFF[min(fail_count - 1, len(RETRY_BACKOFF) - 1)]
            log(f"ERROR ({e}) — retrying in {wait}s "
                f"(attempt {fail_count})")
            time.sleep(wait)
            continue
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
