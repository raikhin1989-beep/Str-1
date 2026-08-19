# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A site in `site/`, deployed over SSH to the **same server that already hosts the sibling project [`raikhin1989-beep/Str`](https://github.com/raikhin1989-beep/Str)** (a birthday invitation site live at `https://raikhin.duckdns.org/`).

**What this is becoming:** a web app for a whisky tasting competition — public whisky lookup by name or bottle photo, participant registration, two blind rounds (by nose, then by palate), leaderboard, admin panel, results delivered over Telegram. Live at `https://raikhinwhiskey.duckdns.org/`. The plan and its acceptance criteria are in [`docs/PLAN.md`](docs/PLAN.md); architecture, data model, scoring rules and operations live alongside it in `docs/`. **Read `docs/PLAN.md` before starting work** — it defines the step the repository is currently on.

The application is built and live: steps 0–11 of the plan are done, step 12 waits for a real evening by its own condition. The app is Python (FastAPI + Jinja2 + SQLite) under `app/`, with pytest gating the deploy; `site/` holds only what Caddy serves as files — `healthz`, the fallback page and `static/`. There is no frontend build and no npm on the server; run the tests with `pytest -q`. See `docs/ARCHITECTURE.md` for the map and `docs/RUNBOOK.md` for what to do when something breaks. `docs/EVENING.md` is the host's script for running an actual tasting — step by step, including which GitHub action to press and when; it doubles as a description of the intended flow, so check it when changing the admin's wording or the order of statuses.

## Sharing a server with `Str` — read before touching the deploy

`Str`'s deploy is destructive to anything it doesn't own: it rsyncs `/var/www/html` with `--delete` and **regenerates `/etc/caddy/Caddyfile` from scratch on every run**. So this repository owns a disjoint set of paths:

| | `Str` | this repo |
| --- | --- | --- |
| Docroot | `/var/www/html` | `/var/www/str-1` |
| Own web server config | `/etc/caddy/Caddyfile` | `/etc/caddy/str-1.caddyfile` |
| Own service | `caddy.service` | `str-1-site.service` |
| Own ports | 80, 443 | 8081 |

Step 1 of the plan adds `str-1-app.service` on `127.0.0.1:8082` and a SQLite database at `/var/lib/str-1/app.db`. The database is deliberately **outside** `/var/www/str-1`: the docroot is rsynced with `--delete`, so anything there that doesn't come from `site/` is erased on the next deploy. See `docs/ARCHITECTURE.md`.

The site is served two ways, on purpose:

- **Port 8081**, by a second Caddy instance (`str-1-site.service`) that this repo fully controls. It depends on nothing external, so it stays reachable even when DNS or the neighbour's config is broken. That instance needs `admin off` in its global options block — the admin endpoint defaults to `127.0.0.1:2019`, which the main Caddy already holds, and without that line the process refuses to start.
- **The domain over HTTPS**, by the *main* Caddy, because ports 80 and 443 can only belong to one process. This deploy never edits `/etc/caddy/Caddyfile` — `Str` would revert it. Instead `Str`'s generated config ends with `import /etc/caddy/sites.d/*.caddy`, and this deploy writes `/etc/caddy/sites.d/str-1.caddy`, validates the *combined* config, and reloads.

That import is a contract with the other repository. If it disappears from `Str`, this deploy fails loudly rather than reporting success with dead HTTPS. Because the neighbour's `caddy validate` also covers our file, a malformed block here breaks *their* deploy — so validation happens before the reload, and the file is removed again if it does not pass.

## Deploy

`.github/workflows/deploy.yml` is the only executable logic. Push to `main` deploys (filtered to `site/**` and the workflow itself, so doc-only commits don't redeploy); `workflow_dispatch` also offers a read-only `inspect` action that probes services, ports and disk without changing anything.

Files travel by `rsync` over `sshpass`, not through the ssh-action's `envs` — that path silently stops delivering once the payload grows past a few hundred KB.

Configured through repository secrets (Settings → Secrets and variables → Actions):

| Secret | Required | Default |
| --- | --- | --- |
| `SERVER_HOST` | yes | — |
| `SERVER_PASSWORD` | yes | — |
| `SERVER_USER` | no | `root` |
| `SERVER_PORT` | no | `22` |
| `DUCKDNS_SUBDOMAIN` | for HTTPS | — (label only, no `.duckdns.org` suffix) |
| `DUCKDNS_TOKEN` | for HTTPS | — |

Authentication is SSH **password**, not a key, and deploys run as `root` by default. These are separate secrets from `Str`'s, even though both point at the same machine.

Which name the certificate is issued for is controlled by the workflow-level `TLS_MODE` env var, not by a secret: `duckdns` uses `<DUCKDNS_SUBDOMAIN>.duckdns.org`, `off` skips the domain entirely. With `TLS_MODE: duckdns` but the DuckDNS secrets unset, the deploy warns and serves port 8081 only — it does not fail, because the subdomain has to be created by hand first.

**DuckDNS has no API for creating a subdomain** — their spec covers only IP and TXT updates for names that already exist. Registration is a manual step in their web UI behind an OAuth login; the workflow can only point an existing subdomain at the server.

## Verifying a deploy

The workflow writes the deployed commit SHA to `<docroot>/version` as its **last** step, after the file sync and the health check — a fresh SHA therefore means the run finished, not merely that it published files. A stale SHA means the run failed or is still running.

```
curl http://<SERVER_HOST>:8081/version        # deployed commit SHA
curl http://<SERVER_HOST>:8081/healthz        # -> ok
curl https://<SITE_DOMAIN>/version            # same SHA, served by the main Caddy
```

Both entrances must report the same SHA — they read the same docroot, so a mismatch means one of the two Caddy instances is serving something stale.

`healthz` is a real file in `site/` and must keep returning `ok` — it is the health contract. `version` is generated at deploy time and is not stored in `site/`.

## Conventions

Comments in `deploy.yml` and user-facing copy in `site/` are written in Russian. Match the surrounding language when editing those files.
