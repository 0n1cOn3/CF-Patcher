#!/usr/bin/env python3
"""CF-Patcher — Cloudflare DynDNS updater.

Auth (pick one):
  CF_API_TOKEN              — recommended, scoped API token (Zone:Read + DNS:Edit)
  CF_API_EMAIL + CF_API_KEY — fallback, Global API Key

Config via config.json (see config.example.json) or CF_PATCHER_CONFIG env
pointing to another JSON file. Secrets NEVER go into the JSON — env only.
"""

import json
import os
import sys
import time

import requests

IP_ENDPOINTS = {
    "ipv4": [
        "https://cloudflare.com/cdn-cgi/trace",  # ip=1.2.3.4 line
        "https://api4.ipify.org",
        "https://v4.ifconfig.me/ip",
    ],
    "ipv6": [
        "https://api6.ipify.org",
        "https://v6.ifconfig.me/ip",
    ],
}
IP_TIMEOUT = 10
CHECK_INTERVAL = int(os.environ.get("CF_CHECK_INTERVAL", "300"))  # seconds
RETRY_BACKOFF = (10, 60, 300, 900)


def log(msg):
    print(msg, flush=True)


def auth_headers():
    token = os.environ.get("CF_API_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    email = os.environ.get("CF_API_EMAIL")
    key = os.environ.get("CF_API_KEY")
    if email and key:
        return {"X-Auth-Email": email, "X-Auth-Key": key}
    sys.exit("No auth: set CF_API_TOKEN or CF_API_EMAIL+CF_API_KEY")


def _is_ipv4(ip):
    return ":" not in ip


def get_public_ip(family="ipv4"):
    """Query multiple endpoints; require a strict majority for one answer."""
    answers = {}
    for url in IP_ENDPOINTS[family]:
        try:
            r = requests.get(url, timeout=IP_TIMEOUT)
            r.raise_for_status()
            ip = (r.text.split("ip=")[1].split()[0] if "ip=" in r.text
                  else r.text.strip())
            if ip and _is_ipv4(ip) == (family == "ipv4"):
                answers[ip] = answers.get(ip, 0) + 1
        except Exception as e:
            log(f"IP endpoint {url} failed: {e}")
    if not answers:
        raise RuntimeError(f"no {family} answer from any endpoint")
    top_ip, top_n = max(answers.items(), key=lambda kv: kv[1])
    if top_n < 2 and len(answers) > 1:
        raise RuntimeError(f"endpoints disagree, no majority: {answers}")
    return top_ip


def cf_request(method, path, headers, data=None):
    r = requests.request(method, f"https://api.cloudflare.com/client/v4{path}",
                         headers=headers, json=data, timeout=30)
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"CF API {path}: {body.get('errors')}")
    return body["result"]


def cf_paginate(path, headers):
    """Yield results across all pages (per_page=50)."""
    page = 1
    while True:
        result = cf_request("GET", f"{path}{'&' if '?' in path else '?'}"
                            f"per_page=50&page={page}", headers)
        yield from result
        if len(result) < 50:
            return
        page += 1


def find_zone_id(headers, domain):
    for zone in cf_paginate("/zones", headers):
        if zone["name"] == domain:
            return zone["id"]
    raise RuntimeError(f"zone not found: {domain}")


def find_record(headers, zone_id, name, rtype):
    """Find exactly one DNS record of the given type and name."""
    recs = [r for r in cf_paginate(f"/zones/{zone_id}/dns_records", headers)
            if r["name"] == name and r["type"] == rtype]
    if not recs:
        raise RuntimeError(f"record not found: {name} ({rtype})")
    if len(recs) > 1:
        raise RuntimeError(f"ambiguous: {len(recs)} {rtype} records for {name} "
                           f"— specify record id explicitly in config")
    return recs[0]


def substitute(record, variables):
    for key, val in variables.items():
        record = {k: (v.replace("{{" + key + "}}", val) if isinstance(v, str)
                      else v) for k, v in record.items()}
    return record


def patch_record(headers, zone_id, rec, ip):
    """Resolve one record (by id or name) and patch it. No cross-record state."""
    r = dict(rec["value"])
    rtype = r.get("type", "A")
    if rec.get("name") and not rec.get("id"):
        found = find_record(headers, zone_id, rec["name"], rtype)
        rec = dict(rec, id=found["id"])
        r.setdefault("type", found["type"])
        r.setdefault("name", found["name"])
        r.setdefault("ttl", found["ttl"])
        r.setdefault("proxied", found["proxied"])
    r.setdefault("ttl", 60)
    rtype = r.get("type", "A")
    record_ip = ip
    if rtype == "AAAA":
        record_ip = get_public_ip("ipv6")
    r = substitute(r, {"public_ip": record_ip})
    cf_request("PATCH", f"/zones/{zone_id}/dns_records/{rec['id']}",
               headers, r)
    log(f"updated {r.get('name', rec.get('id'))} -> {record_ip}")


def patch_account(headers, account, ip):
    """Patch all records of one account; raises at the end if any failed."""
    zone_id = account.get("zone_id") or find_zone_id(headers, account["domain"])
    failures = []
    for rec in account["dns_records"]:
        try:
            patch_record(headers, zone_id, rec, ip)
        except Exception as e:
            log(f"ERROR updating record {rec.get('name', rec.get('id'))}: {e} "
                f"(continuing with the rest)")
            failures.append(rec.get("name", rec.get("id")))
    if failures:
        raise RuntimeError(f"patch failed for: {', '.join(failures)}")


def main():
    cfg_path = os.environ.get("CF_PATCHER_CONFIG", "config.json")
    config = json.load(open(cfg_path))
    headers = auth_headers()
    last_ip = None
    fail_count = 0
    while True:
        try:
            ip = get_public_ip("ipv4")
            if ip != last_ip:
                failures = []
                for account in config:
                    try:
                        patch_account(headers, account, ip)
                    except Exception as e:
                        log(f"ERROR account failed: {e} (continuing)")
                        failures.append(account.get("domain", "account"))
                if failures:
                    raise RuntimeError(f"accounts failed: {', '.join(failures)}")
                last_ip = ip
            else:
                log("IP unchanged, nothing to do")
            fail_count = 0  # full cycle completed successfully
        except Exception as e:
            fail_count += 1
            wait = RETRY_BACKOFF[min(fail_count - 1, len(RETRY_BACKOFF) - 1)]
            log(f"ERROR ({e}) — retrying in {wait}s (attempt {fail_count})")
            time.sleep(wait)
            continue
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
