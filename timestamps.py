"""UTC timestamps in RFC 3339 form without fractional seconds: YYYY-MM-DDTHH:MM:SSZ."""

import re
from datetime import datetime, timezone

_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)")


def _format(value, pattern):
    if value is None:
        value = datetime.now(timezone.utc)
    elif isinstance(value, str):
        if not _STAMP.fullmatch(value):
            return value
        value = datetime.fromisoformat(value)
    elif not isinstance(value, datetime):
        return value
    return value.astimezone(timezone.utc).strftime(pattern)


def utc_stamp(value=None):
    """RFC 3339 UTC timestamp for a datetime or ISO string (default: now); other values pass through."""
    return _format(value, "%Y-%m-%dT%H:%M:%SZ")


def normalize_text(text):
    """Rewrite every ISO timestamp with a UTC offset in text to utc_stamp form."""
    return _STAMP.sub(lambda match: utc_stamp(match.group()), text)
