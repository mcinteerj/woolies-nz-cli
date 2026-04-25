# woolies-nz-cli

Unofficial command-line tool for [Woolworths New Zealand](https://www.woolworths.co.nz). Search products, manage your trolley, and script your shopping — all from the terminal.

```console
$ woolies login
Email: you@example.com
Password: ********
✓ Logged in as you@example.com

$ woolies search milk --limit 3
Found 3 products (3 groups):

Anchor Uht Milk Blue Top
  - Size: 1L (ctn) | Price: $3.40 (Special, was $3.79)
    SKU: 269671 | In Stock | Category: Fridge & Deli
    Unit: Each ($3.40 per 1L)
...

$ woolies cart add 269671 2
✓ Added 2x (SKU: 269671) to cart
```

## What this is / isn't

- ✅ **For:** NZ shoppers who want CLI / scriptable access to Woolworths NZ.
- ✅ **For:** building your own automations on top (rotating shopping lists, price alerts, etc.).
- ❌ **Not:** an official Woolworths product. Hobby-grade, maintained by one person.
- ❌ **Not:** for AU Woolworths or the rebranded Countdown UI — woolworths.co.nz only.
- ❌ **Not:** for redistributing scraped Woolworths product data as a dataset.

> **Disclaimer:** This tool is not affiliated with, endorsed by, or connected to
> Woolworths Limited or Woolworths New Zealand Limited. Use of this tool may
> violate Woolworths' Terms of Service. **Use at your own risk.** The author
> accepts no liability for account suspensions, rate limiting, blocked access,
> or any other consequence of using this software. Consider using a dedicated
> Woolworths account for automated access.

## Stability: it's janky and that's okay

There is no official Woolworths NZ API. This tool works by:

- Driving a real browser to log in (selectors against Woolworths' login page).
- Calling Woolworths' internal `/api/v1/*` endpoints with the resulting cookies (request shapes that Woolworths can change at any time).
- Spoofing browser fingerprints to get past Akamai's bot detection.

**Any of this can break with no warning** — a selector tweak, a payload-shape change, a fingerprint heuristic update. When that happens, this tool will fail with confusing errors until someone (you? me? a passing stranger?) digs in and fixes it.

There are **no uptime promises and no fix-time SLAs**. I'll patch breakage when I can be bothered and have time. If that's not soon enough for you, **PRs are very welcome** — see [CONTRIBUTING.md](CONTRIBUTING.md). A one-line selector fix is a real contribution and will get merged fast.

## Install

> Until the first PyPI release, install from the GitHub repo:

```bash
pipx install git+ssh://git@github.com/mcinteerj/woolies-nz-cli.git
# or, if you prefer HTTPS:
pipx install git+https://github.com/mcinteerj/woolies-nz-cli.git
```

Don't have `pipx`? See [pipx install instructions](https://pipx.pypa.io/stable/installation/), or use plain `pip install` into a venv.

Requires **Python 3.11+**. Tested on macOS (Apple Silicon) and Linux. Windows untested.

## First-run heads-up

Your first command that needs a browser (typically `woolies login`) downloads the **[Camoufox](https://camoufox.com/) browser (~300MB, ~10–60s)**. After that, the browser is cached in `~/Library/Caches/camoufox` (macOS) or `~/.cache/camoufox` (Linux) and reused across runs.

## Setup

```bash
woolies login
```

That's it. It prompts for your Woolworths NZ email + password, runs the browser login (~25s), saves the session cookies, and stores credentials at `~/.config/woolies-nz-cli/config.toml` (mode 0600).

Verify with:

```bash
woolies doctor
```

You'll re-run `woolies login` only when Woolworths invalidates your session (typically every few weeks).

### Alternative: environment variables

For unattended environments (CI, Docker, headless servers, scheduled jobs), skip `woolies login` and set:

```bash
export WOOLWORTHS_USERNAME="you@example.com"
export WOOLWORTHS_PASSWORD="your-password"
```

Env vars override anything in `config.toml`.

### Alternative: `password_command`

If you keep secrets in 1Password / `pass` / Bitwarden / etc., add to `~/.config/woolies-nz-cli/config.toml`:

```toml
username = "you@example.com"
password_command = "op read op://Personal/Woolies/password"
```

The shell command is executed and its stdout is used as the password.

## Usage

### Search

```bash
woolies search "milk"
woolies search "milk" --limit 20
woolies search "milk" --size 2L
woolies search "bread" --json
```

Output groups variants of the same product, shows brand / size / unit price / availability / category, and highlights dual-priced loose produce.

### Search → cart (typical workflow)

```bash
$ woolies search "milk" --limit 3
...
    SKU: 269671 | In Stock | Category: Fridge & Deli
...

$ woolies cart add 269671 2
✓ Added 2x (SKU: 269671) to cart
```

The `SKU` from search output is what `cart add` takes.

### Cart

```bash
woolies cart list
woolies cart add <sku> <quantity>
woolies cart update <sku> <quantity>
woolies cart remove <sku>
woolies cart clear --force
```

Add `--json` to any command for structured output suitable for scripts.

### Dual-priced loose produce

Some loose produce (carrots, onions, apples) supports both `--unit Each` and `--unit Kilogram`:

```bash
woolies cart add 135344 3 --unit Each       # 3 carrots
woolies cart add 135344 0.45 --unit Kilogram # 450g of carrots
```

Search results indicate which products support dual pricing.

### Inspect (debug)

Launches a visible browser with your active session. The browser stays open until Ctrl-C — useful for inspecting selectors, watching API calls in DevTools, or testing the login flow when something breaks:

```bash
woolies inspect
```

### Logout

```bash
woolies logout
```

Removes saved credentials and cookies. Next `woolies login` will start fresh.

## Privacy

- Your credentials and cookies stay on **your machine**. Nothing is uploaded to anywhere except `woolworths.co.nz` itself, with the same data your browser would send when you log in to their website.
- Credentials are stored at `~/.config/woolies-nz-cli/config.toml` with file mode 0600 (owner read/write only).
- Cookies are stored at `~/.local/state/woolies-nz-cli/cookies.json`.
- No telemetry, no analytics, no phone-home. The source is MIT-licensed — read it, audit it, fork it.

## How it works

- **httpx** for fast API calls (~1s per request) using cached cookies.
- **[Camoufox](https://camoufox.com/)** (Firefox-based anti-detect browser) only for initial login or cookie refresh (~25s).
- Sessions persist until Woolworths invalidates them (typically a few weeks).

## File locations

| What | Where |
|------|-------|
| Credentials | `~/.config/woolies-nz-cli/config.toml` (or `$XDG_CONFIG_HOME/woolies-nz-cli/`), mode 0600 |
| Cookies + screenshots | `~/.local/state/woolies-nz-cli/` (or `$XDG_STATE_HOME/woolies-nz-cli/`) |
| Camoufox browser | `~/Library/Caches/camoufox` (macOS) / `~/.cache/camoufox` (Linux) |

## Optional: HTTP proxy for the browser

```bash
export WOOLIES_PROXY="http://user:pass@host:port"
```

Routes the Camoufox browser through a proxy. Useful for residential proxies if Akamai starts blocking your IP.

## Troubleshooting

Run `woolies doctor` first — it diagnoses creds, paths, browser, and DNS in one go.

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Credentials not found` | Haven't logged in | Run `woolies login` |
| `Login failed: invalid credentials` | Wrong username/password | Run `woolies login` again |
| `Could not find email input field` | Woolworths changed login UI | See [CONTRIBUTING.md](CONTRIBUTING.md), or [open an issue](https://github.com/mcinteerj/woolies-nz-cli/issues) |
| `Cannot process request` | API format changed | See [CONTRIBUTING.md](CONTRIBUTING.md) |
| Every run is slow (~25s) | Cookies not persisting | Check `~/.local/state/woolies-nz-cli/` is writable |

To force a fresh login:

```bash
woolies logout && woolies login
```

To report a bug or request a feature: [GitHub issues](https://github.com/mcinteerj/woolies-nz-cli/issues).

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Selector and API-format fixes are especially valuable; even a one-line fix when Woolworths shifts something is a real contribution.

## License

[MIT](LICENSE) © Jake McInteer

The MIT license covers the code only — it does not grant rights to redistribute scraped Woolworths product data as a dataset.
