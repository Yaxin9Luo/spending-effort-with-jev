import re
from collections import Counter

WORD_RE = re.compile(r"[A-Za-z']+")


def count_words(text):
    """Count case-insensitive word frequencies in text."""
    words = (w.lower() for w in WORD_RE.findall(text))
    return Counter(words)
