# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

Initial public release.

### Features

- `woolies search <query>` — search Woolworths NZ products with grouping, dual-priced produce support, size filtering, JSON output.
- `woolies cart {add,list,update,remove,clear}` — full cart management.
- `woolies doctor` — diagnose installation and configuration.
- `woolies inspect` — launch visible browser with active session for debugging.
- Session persistence via cookies in `~/.local/state/woolies-nz-cli/` (XDG-respecting).
- Optional credential config file at `~/.config/woolies-nz-cli/config.toml` (env vars take precedence).
- One-time disclaimer banner on first run.

### Notes

- Requires Python 3.11+.
- Uses Camoufox (Firefox-based anti-detect browser) for authentication; first run downloads the browser (~39s).
- Not affiliated with Woolworths Limited or Woolworths New Zealand Limited.
