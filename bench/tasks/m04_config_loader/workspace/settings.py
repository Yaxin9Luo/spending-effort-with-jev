"""Application settings.

DEFAULTS is the full schema: every valid setting appears here with a default
value, and the type of that default is the setting's type.
"""

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


def load_config(path=None, env=None):
    """Build the effective configuration. See README / ticket."""
    raise NotImplementedError
