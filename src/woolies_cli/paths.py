"""XDG-respecting filesystem paths for woolies-nz-cli."""

import os
from pathlib import Path

APP_NAME = "woolies-nz-cli"


def _xdg_dir(env_var: str, default_subpath: str) -> Path:
    custom = os.getenv(env_var)
    if custom:
        return Path(custom)
    return Path.home() / default_subpath


def state_dir() -> Path:
    """State: cookies, screenshots, first-run marker."""
    return _xdg_dir("XDG_STATE_HOME", ".local/state") / APP_NAME


def config_dir() -> Path:
    """Config: optional credential file."""
    return _xdg_dir("XDG_CONFIG_HOME", ".config") / APP_NAME


def cookies_file() -> Path:
    return state_dir() / "cookies.json"


def storage_file() -> Path:
    return state_dir() / "storage.json"


def screenshot_file(name: str) -> Path:
    return state_dir() / f"{name}.png"


def first_run_marker() -> Path:
    return state_dir() / "first_run_done"


def config_file() -> Path:
    return config_dir() / "config.toml"
