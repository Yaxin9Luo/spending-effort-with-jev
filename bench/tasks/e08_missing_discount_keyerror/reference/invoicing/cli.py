import json
import sys

from invoicing.totals import invoice_savings, invoice_total


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    for path in argv:
        with open(path, encoding="utf-8") as f:
            invoice = json.load(f)
        print(f"{invoice['id']}: total {invoice_total(invoice):.2f}, saved {invoice_savings(invoice):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
