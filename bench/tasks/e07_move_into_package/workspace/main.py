import sys

import loader
from render import render_table


def main(argv):
    if len(argv) < 2:
        print("usage: python3 main.py FILE.csv [COLUMN ...]", file=sys.stderr)
        return 2
    records = loader.load_records(argv[1])
    columns = argv[2:] or list(records[0].keys()) if records else argv[2:]
    print(render_table(records, columns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
