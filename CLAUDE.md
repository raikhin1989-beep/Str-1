# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static site in `site/`, deployed over SSH to the **same server that already hosts the sibling project [`raikhin1989-beep/Str`](https://github.com/raikhin1989-beep/Str)** (a birthday invitation site live at `https://raikhin.duckdns.org/`). At present `site/` is a placeholder page — what this site is actually for has not been decided yet.

There is no build system, package manifest, linter, or test suite. `site/` is hand-written content served as-is; don't assume npm/pip/make targets exist.

## Sharing a server with `Str` — read before touching the deploy

`Str`'s deploy is destructive to anything it doesn't own: it rsyncs `/var/www/html` with `--delete` and **regenerates `/etc/caddy/Caddyfile` from scratch on every run**. So this repository's deploy deliberately shares nothing with it:

| | `Str` | this repo |
| --- | --- | --- |
| Docroot | `/var/www/html` | `/var/www/str-1` |
| Web server config | `/etc/caddy/Caddyfile` | `/etc/caddy/str-1.caddyfile` |
| Service | `caddy.service` | `str-1-site.service` |
| Ports | 80, 443 | 8081 |

The second Caddy instance needs `admin off` in its global options block — the admin endpoint defaults to `127.0.0.1:2019`, which the main Caddy already holds, and without that line the process refuses to start.

**This split is a workaround, not the destination.** Serving this site on a real domain over HTTPS means both projects sharing port 443, which requires one Caddyfile with `import /etc/caddy/sites.d/*.caddy` and a matching change to `Str`'s deploy so it stops overwriting the import. That is a two-repository change — do not half-do it here by writing into `/etc/caddy/Caddyfile`, which `Str` will silently revert on its next deploy.

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

Authentication is SSH **password**, not a key, and deploys run as `root` by default. These are separate secrets from `Str`'s, even though both point at the same machine.

## Verifying a deploy

The workflow writes the deployed commit SHA to `<docroot>/version` as its **last** step, after the file sync and the health check — a fresh SHA therefore means the run finished, not merely that it published files. A stale SHA means the run failed or is still running.

```
curl http://<SERVER_HOST>:8081/version    # deployed commit SHA
curl http://<SERVER_HOST>:8081/healthz    # -> ok
```

`healthz` is a real file in `site/` and must keep returning `ok` — it is the health contract. `version` is generated at deploy time and is not stored in `site/`.

## Conventions

Comments in `deploy.yml` and user-facing copy in `site/` are written in Russian. Match the surrounding language when editing those files.
