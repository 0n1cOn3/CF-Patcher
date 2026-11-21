# 🚀 CF-Patcher

DynDNS for Cloudflare: watches your public IP, patches DNS records on change.

## 🛠️ Run

```bash
cp config.example.json config.json   # edit: your domain + record names
echo CF_API_TOKEN=your-token > .env  # scoped token: Zone:DNS:Edit
docker compose up -d
```

No Dockerfile image rebuild needed for config changes — config is mounted, not baked in.

## 🔐 Auth (env, never in config.json)

Preferred: `CF_API_TOKEN` (create in Cloudflare → My Profile → API Tokens,
template "Edit zone DNS", scoped to your zone). Legacy fallback:
`CF_API_EMAIL` + `CF_API_KEY` (Global API Key — not recommended).

Find zone/record ids (optional — modern config resolves them by name):

```bash
CF_API_TOKEN=xxx DOMAIN=example.com python3 zone-locator.py
```

## ⚙️ Config

`config.json`: list of accounts, each with `domain` and `dns_records`.
Records are matched by `name` (zone/record ids resolved automatically);
`{{public_ip}}` is substituted with the current public IP. See
`config.example.json`.

Env knobs:
- `CF_CHECK_INTERVAL` — seconds between IP checks (default 300)
- `CF_PATCHER_CONFIG` — path to config file (default `config.json`)

## 🔁 Behaviour

- IP via multiple endpoints (Cloudflare trace, ipify, ifconfig.me), majority vote
- Only patches when the IP actually changed
- Failed updates are logged and retried with exponential backoff (10s→15min) — the loop never exits
