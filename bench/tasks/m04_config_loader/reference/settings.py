"""Application settings.

DEFAULTS is the full schema: every valid setting appears here with a default
value, and the type of that default is the setting's type.
"""

import copy
import json
import os

ENV_PREFIX = "MYAPP_"

DEFAULTS = {
    "debug": False,
    "port": 8000,
    "timeout": 2.5,
    "name": "myapp",
    "allowed_hosts": ["localhost"],
    "db": {
        "host": "localhost",
        "port": 5432,
        "user": "app",
        "pool": {"size": 5, "recycle_seconds": 300.0},
    },
    "features": {"beta_ui": False, "tags": []},
}


class ConfigError(Exception):
    """Raised when configuration can't be loaded or is invalid."""


def _merge(base, override, where=""):
    for key, value in override.items():
        if key not in base:
            raise ConfigError(f"unknown setting {where}{key!r}")
        if isinstance(base[key], dict) and isinstance(value, dict):
            _merge(base[key], value, f"{where}{key}.")
        else:
            base[key] = copy.deepcopy(value)


_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


def _coerce(default, raw, var):
    try:
        if isinstance(default, bool):
            v = raw.strip().lower()
            if v in _TRUE:
                return True
            if v in _FALSE:
                return False
            raise ValueError(raw)
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, list):
            return [item.strip() for item in raw.split(",") if item.strip()]
        return raw
    except ValueError:
        raise ConfigError(f"{var}: cannot convert {raw!r} to {type(default).__name__}") from None


def _lookup_default(parts):
    node = DEFAULTS
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            return None, False
        node = node[p]
    if isinstance(node, dict):
        return None, False
    return node, True


def load_config(path=None, env=None):
    """Build the effective configuration: DEFAULTS < JSON file < environment."""
    cfg = copy.deepcopy(DEFAULTS)
    if path is not None:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise ConfigError(f"config file not found: {path}") from None
        except (OSError, ValueError) as e:
            raise ConfigError(f"cannot read config file {path}: {e}") from None
        if not isinstance(data, dict):
            raise ConfigError(f"config file {path} must contain a JSON object")
        _merge(cfg, data)

    if env is None:
        env = os.environ
    for var, raw in env.items():
        if not var.startswith(ENV_PREFIX):
            continue
        parts = var[len(ENV_PREFIX):].lower().split("__")
        default, ok = _lookup_default(parts)
        if not ok:
            continue
        node = cfg
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = _coerce(default, raw, var)
    return cfg
