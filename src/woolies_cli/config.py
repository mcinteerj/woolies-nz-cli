"""Credential resolution and persistence.

Resolution order:
  1. Env vars (WOOLWORTHS_USERNAME / WOOLWORTHS_PASSWORD)
  2. ~/.config/woolies-nz-cli/config.toml direct password
  3. ~/.config/woolies-nz-cli/config.toml password_command
"""

import os
import stat
import subprocess
import tomllib
from pathlib import Path
from typing import Optional

from .paths import config_file


class ConfigError(Exception):
    """Configuration could not be resolved."""


def _resolve_password_from_config(data: dict) -> Optional[str]:
    """Get password from config dict: direct value or password_command output."""
    if data.get("password"):
        return data["password"]
    if data.get("password_command"):
        try:
            result = subprocess.run(
                data["password_command"],
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            raise ConfigError(
                f"password_command failed: {stderr or e}"
            ) from e
    return None


def _read_config() -> dict:
    """Read config.toml or return empty dict."""
    cfg_path = config_file()
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        raise ConfigError(f"Could not read {cfg_path}: {e}") from e


def load_credentials() -> tuple[str, str]:
    """Resolve (username, password). Env > config.toml > password_command."""
    env_user = os.getenv("WOOLWORTHS_USERNAME")
    env_pw = os.getenv("WOOLWORTHS_PASSWORD")

    if env_user and env_pw:
        return env_user, env_pw

    data = _read_config()
    username = env_user or data.get("username")
    password = env_pw or _resolve_password_from_config(data)

    if not username or not password:
        raise ConfigError(
            "Credentials not found. Run `woolies login`, or set "
            "WOOLWORTHS_USERNAME and WOOLWORTHS_PASSWORD environment variables."
        )

    return username, password


def credentials_source() -> Optional[str]:
    """Short human-readable description of where creds resolve from. None if missing."""
    if os.getenv("WOOLWORTHS_USERNAME") and os.getenv("WOOLWORTHS_PASSWORD"):
        return "environment variables"
    data = _read_config()
    if data.get("username"):
        if data.get("password"):
            return f"{config_file()}"
        if data.get("password_command"):
            return f"{config_file()} (password_command)"
    return None


def _format_toml_value(value) -> str:
    """Minimal TOML value emitter for our flat string config."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _write_config(data: dict) -> None:
    """Write config.toml with mode 0600. Removes file if data is empty."""
    cfg_path = config_file()

    if not data:
        if cfg_path.exists():
            cfg_path.unlink()
        return

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k} = {_format_toml_value(v)}" for k, v in data.items()]
    cfg_path.write_text("\n".join(lines) + "\n")
    cfg_path.chmod(0o600)


def save_credentials(username: str, password: str) -> Path:
    """Write credentials to config.toml (mode 0600). Preserves other settings."""
    data = _read_config()
    data["username"] = username
    data["password"] = password
    data.pop("password_command", None)
    _write_config(data)
    return config_file()


def remove_credentials() -> bool:
    """Remove credential keys from config.toml. Returns True if any were present."""
    data = _read_config()
    had_any = any(k in data for k in ("username", "password", "password_command"))
    for k in ("username", "password", "password_command"):
        data.pop(k, None)
    _write_config(data)
    return had_any


def loose_permissions_warning() -> Optional[str]:
    """Return warning if config.toml is group/world readable, else None."""
    cfg_path = config_file()
    if not cfg_path.exists():
        return None
    try:
        mode = cfg_path.stat().st_mode
    except OSError:
        return None
    bad = stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH
    if mode & bad:
        return (
            f"{cfg_path} has loose permissions ({stat.filemode(mode)}). "
            f"Run: chmod 600 {cfg_path}"
        )
    return None
