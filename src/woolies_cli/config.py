"""Credential resolution: env vars → config.toml → error."""

import os
import tomllib

from .paths import config_file


class ConfigError(Exception):
    """Configuration could not be resolved."""


def load_credentials() -> tuple[str, str]:
    """Resolve (username, password). Env vars take precedence over config.toml."""
    username = os.getenv("WOOLWORTHS_USERNAME")
    password = os.getenv("WOOLWORTHS_PASSWORD")

    if username and password:
        return username, password

    cfg_path = config_file()
    if cfg_path.exists():
        try:
            with open(cfg_path, "rb") as f:
                data = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError) as e:
            raise ConfigError(f"Could not read {cfg_path}: {e}") from e
        username = username or data.get("username")
        password = password or data.get("password")

    if not username or not password:
        raise ConfigError(
            "Credentials not found. Set WOOLWORTHS_USERNAME and "
            f"WOOLWORTHS_PASSWORD environment variables, or create {cfg_path} "
            'with:\n\n  username = "you@example.com"\n  password = "..."\n'
        )

    return username, password
