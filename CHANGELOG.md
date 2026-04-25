# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-04-25

### Changed

- Switch build backend from `setuptools` to `hatchling` to drop the
  stray `src/woolies_nz_cli.egg-info/` directory that setuptools includes
  in sdists on src layouts. Wheel and runtime behaviour are unchanged.

## [0.1.0] - 2026-04-25

Initial public release.

### Features

- `woolies login` — interactive login. Prompts for email + password, runs the browser auth flow, caches cookies, and saves credentials to `~/.config/woolies-nz-cli/config.toml` (mode 0600).
- `woolies logout` — removes saved credentials and cookies.
- `woolies search <query>` — search Woolworths NZ products with grouping, dual-priced produce support, size filtering, JSON output.
- `woolies cart {add,list,update,remove,clear}` — full cart management.
- `woolies doctor` — diagnose installation and configuration; reports credential source.
- `woolies inspect` — launch visible browser with active session for debugging.

### Configuration

Credentials resolution order:

1. Environment variables (`WOOLWORTHS_USERNAME` / `WOOLWORTHS_PASSWORD`) — for CI / containers / automation.
2. `~/.config/woolies-nz-cli/config.toml` — populated by `woolies login`.
3. `password_command` in `config.toml` — power-user integration with 1Password / `pass` / Bitwarden / etc.

Loose-permissions warning printed if `config.toml` is group/world readable.

### Notes

- Requires Python 3.11+.
- Uses [Camoufox](https://camoufox.com/) (Firefox-based anti-detect browser) for authentication; first login downloads the browser (~300MB).
- Sessions persist via cookies in `~/.local/state/woolies-nz-cli/` (XDG-respecting).
- One-time disclaimer banner on first run.
- Not affiliated with Woolworths Limited or Woolworths New Zealand Limited.
