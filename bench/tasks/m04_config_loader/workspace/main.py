import sys

from settings import ConfigError, load_config


def main():
    try:
        cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1
    print(f"starting {cfg['name']} on port {cfg['port']} (debug={cfg['debug']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
