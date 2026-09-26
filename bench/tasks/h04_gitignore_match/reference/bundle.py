"""List the files that go into a deploy bundle: everything git wouldn't ignore."""
import os
import sys

from ignorematch import is_ignored


def bundle_files(root):
    gi = os.path.join(root, ".gitignore")
    patterns = open(gi, encoding="utf-8").read().splitlines() if os.path.exists(gi) else []
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            rel = rel_dir + name
            if not is_ignored(rel, patterns):
                out.append(rel)
    return out


if __name__ == "__main__":
    for f in bundle_files(sys.argv[1] if len(sys.argv) > 1 else "."):
        print(f)
