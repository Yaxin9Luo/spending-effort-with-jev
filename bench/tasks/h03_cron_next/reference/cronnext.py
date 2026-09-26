"""Compute when a cron schedule fires next.

Used by the job runner to show "next run" times and to decide what to wake up for.

Semantics follow crontab(5) (Vixie cron / cronie): five fields
(minute hour day-of-month month day-of-week), '*', lists, ranges, steps,
month/day names, 0 or 7 for Sunday, the @-nicknames, and the rule that when
both day-of-month and day-of-week are restricted, a day matches if EITHER does.
"""
from datetime import datetime, timedelta

_NICKNAMES = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = {n: i + 1 for i, n in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}
_DAYS = {n: i for i, n in enumerate("sun mon tue wed thu fri sat".split())}

# (low, high, names)
_FIELDS = [(0, 59, None), (0, 23, None), (1, 31, None), (1, 12, _MONTHS), (0, 7, _DAYS)]

# Far enough to cover any Gregorian pattern (the calendar repeats every 400 years).
_HORIZON_DAYS = 400 * 366 + 7


def _number(tok, low, high, names):
    if names and tok.lower() in names:
        return names[tok.lower()]
    if not tok.isdigit():
        raise ValueError(f"bad value {tok!r}")
    n = int(tok)
    if not low <= n <= high:
        raise ValueError(f"value {n} out of range {low}-{high}")
    return n


def _parse_field(text, low, high, names):
    values = set()
    for item in text.split(","):
        if item == "":
            raise ValueError("empty list item")
        rng, slash, step_s = item.partition("/")
        if slash:
            if not step_s.isdigit() or int(step_s) == 0:
                raise ValueError(f"bad step in {item!r}")
            step = int(step_s)
        else:
            step = 1
        if rng == "*":
            start, stop = low, high
        elif "-" in rng:
            a, _, b = rng.partition("-")
            start, stop = _number(a, low, high, names), _number(b, low, high, names)
        else:
            if slash:
                raise ValueError(f"step needs a range or '*': {item!r}")
            start = stop = _number(rng, low, high, names)
        values.update(range(start, stop + 1, step))
    return values


def _parse(expr):
    if not isinstance(expr, str):
        raise ValueError("expression must be a string")
    text = expr.strip()
    if text.startswith("@"):
        if text.lower() not in _NICKNAMES:
            raise ValueError(f"unsupported nickname {text!r}")
        text = _NICKNAMES[text.lower()]
    fields = text.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    sets = [_parse_field(f, *spec) for f, spec in zip(fields, _FIELDS)]
    minutes, hours, doms, months, dows = sets
    if 7 in dows:
        dows.discard(7)
        dows.add(0)
    dom_star = fields[2].startswith("*")
    dow_star = fields[4].startswith("*")
    return sorted(minutes), sorted(hours), doms, months, dows, dom_star, dow_star


def _day_matches(d, doms, months, dows, dom_star, dow_star):
    if d.month not in months:
        return False
    dom_ok = d.day in doms
    dow_ok = (d.isoweekday() % 7) in dows
    if dom_star or dow_star:
        return dom_ok and dow_ok
    return dom_ok or dow_ok


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first time strictly after `after` at which cron expression `expr` fires.

    Raises ValueError for an invalid expression or one that can never fire.
    """
    minutes, hours, doms, months, dows, dom_star, dow_star = _parse(expr)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    day = start.date()
    for offset in range(_HORIZON_DAYS):
        d = day + timedelta(days=offset)
        if not _day_matches(d, doms, months, dows, dom_star, dow_star):
            continue
        for h in hours:
            for m in minutes:
                cand = datetime(d.year, d.month, d.day, h, m, tzinfo=after.tzinfo)
                if cand >= start:
                    return cand
    raise ValueError(f"cron expression {expr!r} never fires")
