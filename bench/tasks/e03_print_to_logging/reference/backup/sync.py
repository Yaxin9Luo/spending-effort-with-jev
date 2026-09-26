import logging
import os
import shutil

logger = logging.getLogger(__name__)


def sync_dir(src, dst):
    """Copy files from src to dst that are missing or newer there.

    Subdirectories are not recursed into. Returns the number of files copied.
    """
    if not os.path.isdir(src):
        logger.error("source directory not found: %s", src)
        return 0
    os.makedirs(dst, exist_ok=True)
    copied = 0
    for name in sorted(os.listdir(src)):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            logger.warning("skipping subdirectory %s", name)
            continue
        if os.path.exists(d) and os.path.getmtime(d) >= os.path.getmtime(s):
            logger.debug("up to date: %s", name)
            continue
        shutil.copy2(s, d)
        logger.info("copied %s", name)
        copied += 1
    logger.info("done: %d file(s) copied", copied)
    return copied
