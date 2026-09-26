import os
import shutil


def sync_dir(src, dst):
    """Copy files from src to dst that are missing or newer there.

    Subdirectories are not recursed into. Returns the number of files copied.
    """
    if not os.path.isdir(src):
        print(f"ERROR: source directory not found: {src}")
        return 0
    os.makedirs(dst, exist_ok=True)
    copied = 0
    for name in sorted(os.listdir(src)):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            print(f"WARNING: skipping subdirectory {name}")
            continue
        if os.path.exists(d) and os.path.getmtime(d) >= os.path.getmtime(s):
            print(f"up to date: {name}")
            continue
        shutil.copy2(s, d)
        print(f"copied {name}")
        copied += 1
    print(f"done: {copied} file(s) copied")
    return copied
