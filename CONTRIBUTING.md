# Contributing

Contributions welcome — particularly fixes for selectors and API formats when Woolworths NZ changes their site.

## Development setup

```bash
git clone git@github.com:mcinteerj/woolies-nz-cli.git
cd woolies-nz-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Set credentials (use a dedicated test account):

```bash
export WOOLWORTHS_USERNAME="..."
export WOOLWORTHS_PASSWORD="..."
```

## Most likely things to break

This is screen-scraping plus undocumented-API-calling. There is no SLA. Selector tweaks and API payload changes are the bread and butter of breakage here — and your selector-fix PR is a genuine contribution. Don't worry about scope.

Woolworths updates their site regularly. The two failure modes:

### 1. Login selectors change (`src/woolies_cli/browser.py`)

Symptom: `Could not find email input field` or timeout on login.

Fix:
1. Run `woolies inspect` to launch a visible browser with your session.
2. Click "Sign in", inspect the DOM with browser devtools.
3. Update the selectors in `browser.py` (`login` method).

### 2. API format changes (`src/woolies_cli/client.py`, `http_client.py`)

Symptom: `Cannot process request` or unexpected fields missing.

Fix:
1. Run `woolies inspect`.
2. Open the Network tab in browser devtools.
3. Manually perform the operation in the UI.
4. Find the matching `/api/v1/...` request, copy the payload.
5. Compare with what `client.py` is sending. Adjust as needed.

## Code style

- Ruff for formatting + linting (`ruff format`, `ruff check`)
- Mypy for type checking (`mypy src/`)
- Pre-commit-friendly. CI runs both.

## Pull requests

- Keep changes focused. One concern per PR.
- Include a brief description of what broke + how you found the fix.
- Test against your own Woolworths NZ account before submitting.

## Selector / API change PRs are especially welcome

These are high-signal contributions because they only happen when something has materially broken. Even a one-line selector fix is a real contribution.

## What this project is not

- An officially-supported integration.
- A SaaS product or business.
- A tool for redistributing scraped Woolworths product data.

If you want to build any of those, please don't use this code as the foundation without a separate conversation.
