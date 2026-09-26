import tomllib
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.toml"


def load_settings(path=DEFAULT_PATH):
    """Load the service settings from a TOML file into a plain dict."""
    with open(path, "rb") as f:
        return tomllib.load(f)
