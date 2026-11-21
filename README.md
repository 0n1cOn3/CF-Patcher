# 🚀 CF-Patcher

DynDNS for Cloudflare: watches your public IP and patches your DNS records when
it changes. Docker-first, but runs fine as a bare Python script.

## ✨ Features

- **Scoped API token auth** — no Global API Key needed (still supported as legacy fallback)
- **Secrets via environment only** — nothing sensitive in config files or the image
- **Zone/record auto-discovery** — configure by domain + record name, no manual ID lookups
- **Multi-endpoint IP detection** — Cloudflare trace, ipify, ifconfig.me with majority vote
- **Resilient loop** — never exits on API errors: exponential backoff retry (10s → 15 min),
  patches re-attempted until every record succeeded
- **Docker**: python:3.12-slim, non-root user, config mounted read-only

## 🚀 Quickstart (Docker)

```bash
git clone https://github.com/0n1cOn3/CF-Patcher.git
cd CF-Patcher

cp config.example.json config.json   # edit: your domain + record names
echo CF_API_TOKEN=*** > .env         # scoped token (see below)
chmod 600 .env config.json
# container runs as UID 1000 — make sure it can read config.json:
#   chown 1000: config.json   (or chmod 644)

docker compose up -d
docker compose logs -f
```

The container restarts automatically (`restart: always`).

## 🐍 Bare metal / systemd

Requires Python 3.11+ and `requests`:

```bash
pip install -r requirements.txt
cp config.example.json config.json   # then edit
export CF_API_TOKEN=***
python3 main.py
```

## 🔐 Authentication (environment)

| Variable | Meaning |
|---|---|
| `CF_API_TOKEN` | **Recommended.** Scoped API token: Cloudflare → My Profile → API Tokens → *Create Token* → template **"Edit zone DNS"**, restricted to your zone. Auto-discovery also reads the zone/record list, so include **Zone → Zone → Read** for the zone |
| `CF_API_EMAIL` + `CF_API_KEY` | Legacy fallback: account email + Global API Key. Grants full account access — use only if you must |

Never put credentials in `config.json` — it may be mounted/shared.

Optional helpers:

```bash
# list zone + record ids (useful for legacy id-based config)
CF_API_TOKEN=*** DOMAIN=example.com python3 zone-locator.py
```

## ⚙️ Configuration

`config.json` (override path with `CF_PATCHER_CONFIG`):

```json
[
  {
    "domain": "example.com",
    "dns_records": [
      {
        "name": "home.example.com",
        "value": { "content": "{{public_ip}}", "ttl": 60, "proxied": false }
      }
    ]
  }
]
```

- `domain` — zone is resolved automatically (or set `zone_id` explicitly)
- `dns_records[].name` — record is resolved by name **and type** (default `A`);
  omit `proxied`/`ttl` in `value` to preserve the record's existing settings;
  ambiguous duplicates are rejected instead of guessed. Legacy: set `id` instead of `name`.
- `{{public_ip}}` — substituted with the current public IP (majority vote across endpoints)

Environment knobs:

| Variable | Default | Meaning |
|---|---|---|
| `CF_CHECK_INTERVAL` | `300` | Seconds between IP checks |
| `CF_PATCHER_CONFIG` | `config.json` | Path to config file |

## 🔁 Behaviour

- IP is detected once per cycle and used consistently for all updates
- Records are patched only when the IP changed
- If any record fails, the new IP is **not** committed — the next cycle retries everything
- API/network failures: logged, retried with backoff 10s → 60s → 300s → 900s (stays at 900s)
- IPv6: records of type `AAAA` are patched from a separately detected IPv6 address
- Unchanged IP: nothing is written

## 🛡️ Security notes

- TLS verification is always on
- Config is mounted read-only in Docker (`:ro`), secrets live in `.env` (never committed — see `.gitignore`)
- Prefer a token scoped to a single zone over the Global API Key

## 📄 License

As-is, no warranty. Use at your own risk.
