# woolies-nz-cli

Unofficial command-line tool for [Woolworths New Zealand](https://www.woolworths.co.nz). Search products and manage your cart from the terminal.

> **Disclaimer:** This tool is not affiliated with, endorsed by, or connected to
> Woolworths Limited or Woolworths New Zealand Limited. Use of this tool may
> violate Woolworths' Terms of Service. **Use at your own risk.**
>
> The author accepts no liability for account suspensions, rate limiting, blocked
> access, or any other consequence of using this software. Consider using a
> dedicated Woolworths account for automated access.

## Install

```bash
pipx install woolies-nz-cli
```

Or with `pip`:

```bash
pip install woolies-nz-cli
```

Requires Python 3.11+.

## Setup

Set your Woolworths NZ account credentials as environment variables:

```bash
export WOOLWORTHS_USERNAME="you@example.com"
export WOOLWORTHS_PASSWORD="your-password"
```

Or create a config file at `~/.config/woolies-nz-cli/config.toml`:

```toml
username = "you@example.com"
password = "your-password"
```

(Environment variables take precedence over the config file.)

Verify with:

```bash
woolies doctor
```

## Usage

### Search

```bash
woolies search "milk"
woolies search "milk" --limit 20 --size 2L
woolies search "bread" --json
```

Output groups variants of the same product, shows brand / size / unit price / availability / category, and highlights dual-priced loose produce (items priced both per-each and per-kg).

### Cart

```bash
woolies cart list
woolies cart add 910393 2
woolies cart add 135344 0.45 --unit Kilogram
woolies cart update 910393 3
woolies cart remove 910393
woolies cart clear --force
```

### Dual-priced loose produce

Some loose produce (carrots, onions, apples) supports both `--unit Each` and `--unit Kilogram` / `--unit Kg`:

```bash
woolies cart add 135344 3 --unit Each       # 3 carrots
woolies cart add 135344 0.45 --unit Kilogram # 450g of carrots
```

Search results indicate when a product supports dual pricing.

### Inspect (debug)

Launches a visible browser with your active session — useful when selectors break:

```bash
woolies inspect
```

## How it works

- **httpx** for fast API calls (~1s per request) using cached cookies.
- **Camoufox** (Firefox-based anti-detect browser) only for initial login or cookie refresh (~25s).
- Sessions cached at `~/.local/state/woolies-nz-cli/cookies.json` and persist until Woolworths invalidates them (typically ≥30 days).

On first run the Camoufox browser is downloaded (~200MB, ~39s). Subsequent runs reuse it.

## File locations

| What | Where |
|------|-------|
| Cookies + screenshots | `~/.local/state/woolies-nz-cli/` (or `$XDG_STATE_HOME/woolies-nz-cli/`) |
| Optional config file | `~/.config/woolies-nz-cli/config.toml` (or `$XDG_CONFIG_HOME/woolies-nz-cli/`) |

## Reset session

Force a fresh login:

```bash
rm -rf ~/.local/state/woolies-nz-cli/
```

## Optional: HTTP proxy for the browser

Set `WOOLIES_PROXY=http://user:pass@host:port` to route Camoufox through a proxy. Useful for residential proxies if Akamai blocks your IP.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Credentials not found` | Env vars not set | Set `WOOLWORTHS_USERNAME` / `WOOLWORTHS_PASSWORD`, or create config file |
| `Login failed: invalid credentials` | Wrong username/password | Check credentials |
| `Could not find email input field` | Woolworths changed login UI | See [CONTRIBUTING.md](CONTRIBUTING.md) |
| `Cannot process request` | API format changed | See [CONTRIBUTING.md](CONTRIBUTING.md) |
| Every run is slow (~25s) | Session not persisting | Check `~/.local/state/woolies-nz-cli/` is writable |

Run `woolies doctor` for a diagnostic report.

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Selector and API-format fixes are especially valuable.

## License

[MIT](LICENSE) © Jake McInteer

This software is provided "as is", without warranty of any kind. The MIT license covers the code only — it does not grant rights to redistribute scraped Woolworths product data as a dataset.
