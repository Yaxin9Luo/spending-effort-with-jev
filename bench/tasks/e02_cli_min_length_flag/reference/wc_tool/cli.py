import argparse
import sys

from wc_tool.counter import count_words


def build_parser():
    p = argparse.ArgumentParser(prog="wc_tool", description="Count word frequencies in a text file.")
    p.add_argument("path", help="text file to read")
    p.add_argument("--top", type=int, default=10, help="how many words to show (default: 10)")
    p.add_argument("--min-length", type=int, default=1,
                   help="only count words at least this many characters long (default: 1)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    with open(args.path, encoding="utf-8") as f:
        text = f.read()
    counts = count_words(text, min_length=args.min_length)
    for word, n in counts.most_common(args.top):
        print(f"{n}\t{word}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
