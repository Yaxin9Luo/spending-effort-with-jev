import logging
import sys

from backup.sync import sync_dir

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    src, dst = sys.argv[1], sys.argv[2]
    sync_dir(src, dst)
