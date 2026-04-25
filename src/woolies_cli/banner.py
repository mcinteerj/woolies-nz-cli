"""One-time disclaimer banner shown on first run."""

import sys

from .paths import first_run_marker, state_dir

BANNER = """\
WARNING: woolies-nz-cli automates interactions with Woolworths NZ.
Your account may be flagged or suspended for automated usage.
Use a dedicated account if possible.

This tool is not affiliated with Woolworths Limited or Woolworths
New Zealand Limited. Use at your own risk. See README for details.
"""


def maybe_show_banner() -> None:
    """Print disclaimer once, then create a marker so subsequent runs are silent."""
    marker = first_run_marker()
    if marker.exists():
        return

    print(BANNER, file=sys.stderr)
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        # Non-fatal — banner just shows again next run.
        pass
