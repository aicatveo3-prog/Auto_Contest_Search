import re

_SECTION_BREAK = re.compile(r"[■□●○▶▷※]")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_URL_RE = re.compile(r"https?://[^\s)\]>\"']+")

_SPACE_FIXES = [
    ("대 상", "대상"), ("주 제", "주제"), ("공모 접수", "공모접수"),
    ("접 수", "접수"), ("제 출", "제출"), ("공 모", "공모"),
    ("시 간", "시간"), ("장 소", "장소"), ("내 용", "내용"),
]

_TASK_KEYS = ["공모내용", "공모분야", "응모분야", "모집분야", "출품내용", "공모부문",
              "공모품목", "공모종목", "종목", "공모내역", "제출물", "출품물", "제출서류",
              "작품내용", "공모작", "과제", "제작내용"]
_TOPIC_KEYS = ["공모주제", "응모주제", "작품주제", "공모테마", "주제"]
_FORMAT_KEYS = ["출품규격", "공모형식", "제출규격", "공모규격", "규격", "분량", "파일형식", "형식"]
_TARGET_KEYS = ["응모대상", "공모대상", "참가대상", "지원자격", "참가자격",
                "응모자격", "신청자격", "참가조건", "대상"]
_SUBMIT_KEYS = ["공모접수", "접수방법", "제출방법", "응모방법", "접수처", "제출처"]

_NOTE_MARKERS = "※*"
_NOTE_WORDS = ("금지", "불가", "제한", "허용", "유의", "주의")


def _normalize_spacing(text):
    for source, target in _SPACE_FIXES:
        text = text.replace(source, target)
    return text


def _clean(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[\s■□●○▶▷·•\-\*]+", "", text).strip()
    text = re.sub(r"^[①-⑳]\s*", "", text).strip()
    text = text.strip(" -·•/|")
    if len(text) > 150:
        text = text[:149].rstrip() + "…"
    return text


def _after(text, keys, limit=180):
    for key in keys:
        index = text.find(key)
        if index < 0:
            continue
        remainder = text[index + len(key):].lstrip(" :：-•·>|")
        match = _SECTION_BREAK.search(remainder)
        segment = remainder[:match.start()] if match else remainder[:limit]
        value = _clean(segment)
        if len(value) >= 2:
            return value
    return None


def _submit(text):
    value = _after(text, _SUBMIT_KEYS)
    email = _EMAIL_RE.search(text)
    url = _URL_RE.search(text)
    contact = email.group(0) if email else (url.group(0) if url else None)
    if value and contact and contact not in value:
        value = f"{value} ({contact})"
    elif not value and contact:
        value = contact
    return value


def _notes(text):
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        marked = line[0] in _NOTE_MARKERS
        strong = any(word in line for word in _NOTE_WORDS)
        if not (marked or strong):
            continue
        value = _clean(line)
        if len(value) >= 4 and value not in out:
            out.append(value)
        if len(out) >= 3:
            break
    return " / ".join(out) if out else None


def extract_fields(body_text, eligibility=None):
    if not body_text:
        return {"task": None, "topic": None, "format": None,
                "target": eligibility, "submit": None, "notes": None}

    text = _normalize_spacing(body_text)
    return {
        "task": _after(text, _TASK_KEYS),
        "topic": _after(text, _TOPIC_KEYS),
        "format": _after(text, _FORMAT_KEYS),
        "target": eligibility or _after(text, _TARGET_KEYS),
        "submit": _submit(text),
        "notes": _notes(text),
    }
