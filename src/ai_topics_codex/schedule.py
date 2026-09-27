"""UTC five-field cron, including Vixie day-of-month/day-of-week OR semantics."""

from datetime import datetime


def field_values(field, low, high):
    values = set()
    for item in field.split(","):
        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError(f"invalid cron field: {field}")
        base = parts[0]
        step = int(parts[1]) if len(parts) == 2 else 1
        if step <= 0:
            raise ValueError("cron step must be positive")
        if base == "*":
            start, end = low, high
        elif "-" in base:
            start, end = map(int, base.split("-"))
        else:
            start = int(base)
            end = high if len(parts) == 2 else start
        if not low <= start <= end <= high:
            raise ValueError(f"cron field out of range: {field}")
        values.update(range(start, end + 1, step))
    return values


def cron_matches(expr: str, when: datetime):
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron requires five fields")
    minute, hour, dom, month, dow = [
        field_values(f, *r)
        for f, r in zip(fields, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)])
    ]
    day = (when.weekday() + 1) % 7
    dm = when.day in dom
    dw = day in dow or (day == 0 and 7 in dow)
    day_match = (
        (dm and dw)
        if fields[2].startswith("*") or fields[4].startswith("*")
        else (dm or dw)
    )
    return (
        when.minute in minute
        and when.hour in hour
        and when.month in month
        and day_match
    )
