import re
from datetime import date, datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9))
PRIORITY_DAYS = 7
STATUS_LABELS = {"ing": "접수중", "future": "접수예정", "end": "마감", "unknown": "일정 확인"}

_DATE = re.compile(
    r"^\s*(?:(?P<year>\d{4})\s*(?:[./-]|년)\s*)?"
    r"(?P<month>\d{1,2})\s*(?:[./-]|월)\s*(?P<day>\d{1,2})(?!\d)(?:\s*[.일])?"
)
_CLOCK = re.compile(
    r"^\s*(?:\([월화수목금토일](?:요일)?\)|[월화수목금토일]요일)?"
    r"\s*(?P<period>오전|오후)?\s*(?P<hour>\d{1,2})"
    r"(?::(?P<minute>\d{2})(?::(?P<second>\d{2}))?|\s*시(?:\s*(?P<kminute>\d{1,2})\s*분)?)"
    r"(?![\d:])"
)
_DEADLINE = re.compile(
    r"(?:접수|신청|응모|제출|모집|공모)\s*(?:기간|마감|기한|일정)|"
    r"(?:작품\s*)?(?:접수|신청|응모|제출)\s*[:：]"
)
PERIOD_SEPARATOR = re.compile(r"[~～∼〜]|\s+[–—-]\s+")


def now_kst():
    return datetime.now(KST)


def _date_and_time(value, default_year=None):
    match = _DATE.match(value or "")
    if not match or not (match["year"] or default_year):
        return None, None
    try:
        day = date(int(match["year"] or default_year), int(match["month"]), int(match["day"]))
    except ValueError:
        return None, None
    tail = value[match.end():]
    if tail.startswith("T"):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return day, None
        if timestamp.tzinfo:
            timestamp = timestamp.astimezone(KST)
        return timestamp.date(), timestamp.time()
    clock = _CLOCK.match(tail)
    if not clock:
        return day, None
    hour = int(clock["hour"])
    minute = int(clock["minute"] or clock["kminute"] or 0)
    second = int(clock["second"] or 0)
    if clock["period"]:
        if not 1 <= hour <= 12:
            return day, None
        hour = hour % 12 + (12 if clock["period"] == "오후" else 0)
    if hour == 24 and minute == second == 0:
        return day, time.max
    try:
        return day, time(hour, minute, second)
    except ValueError:
        return day, None


def _deadline_in_body(body, deadline_day):
    # The same date can appear in result or event times. Only use reception lines.
    candidates = set()
    follows_heading = False
    for line in (body or "").splitlines():
        line = line.strip()
        if not line:
            continue
        heading = _DEADLINE.search(line)
        if not heading and not follows_heading:
            continue
        follows_heading = bool(heading and not line[heading.end():].strip(" :："))
        if follows_heading:
            continue
        value = line[heading.end():] if heading else line
        value = PERIOD_SEPARATOR.split(value)[-1].lstrip(" :：-·•")
        day, clock = _date_and_time(value, deadline_day.year)
        if day == deadline_day and clock is not None:
            candidates.add(clock)
    if len(candidates) == 1:
        return candidates.pop()
    return None


def schedule_bounds(row):
    start_day, start_clock = _date_and_time(row.get("start_date"))
    end_day, end_clock = _date_and_time(row.get("end_date"), start_day.year if start_day else None)
    if start_day and end_day and end_day < start_day:
        return None, None
    start = datetime.combine(start_day, start_clock or time.min, KST) if start_day else None
    if not end_day:
        return start, None
    if end_clock is None:
        end_clock = _deadline_in_body(row.get("body_text"), end_day) or time.max
    end = datetime.combine(end_day, end_clock, KST)
    return (None, None) if start and end < start else (start, end)


def schedule_status(start, end, now):
    if end and now > end:
        return "end"
    if start and now < start:
        return "future"
    if start and end:
        return "ing"
    return "unknown"
