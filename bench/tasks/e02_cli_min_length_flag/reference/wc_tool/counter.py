import re
from collections import Counter

WORD_RE = re.compile(r"[A-Za-z']+")


def count_words(text, min_length=1):
    """Count case-insensitive word frequencies in text.

    Words shorter than min_length characters are ignored.
    """
    words = (w.lower() for w in WORD_RE.findall(text) if len(w) >= min_length)
    return Counter(words)
