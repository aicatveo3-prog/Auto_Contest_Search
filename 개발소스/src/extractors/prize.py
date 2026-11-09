import re

RANK_ORDER = [
    "그랑프리", "대상", "최우수상", "최우수", "금상", "은상", "동상",
    "우수상", "우수", "장려상", "장려", "특별상", "입선", "가작",
    "1등", "2등", "3등",
]

_RANK_RE = re.compile("|".join(sorted((re.escape(r) for r in RANK_ORDER), key=len, reverse=True))
                      + r"|(?<!\d)([1-3])\s*위")

_AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s*(억|천만|백만|만|천)?\s*원")
_COUNT_RE = re.compile(r"(\d+)\s*(?:명|팀|점|작품|개|인|편)")
_PAREN_COUNT_RE = re.compile(r"[(（]\s*(\d+)\s*(?:점|명|팀|개|편|작품)?\s*[)）]")

_SECTION_RE = re.compile(r"시상\s*(?:내역|내용|금|규모|계획|안내)?")
_STOP_RE = re.compile(r"^(?:■|□|●|○|▶|※)?\s*(문의|접수|유의|심사|응모|제출|기타|주최|주관)")
_TOTAL_RE = re.compile(r"총\s*(?:상금|시상금|상금액|시상)\s*[:：]?\s*(?:총\s*)?[^\n]*?(\d{1,3}(?:,\d{3})+|\d+)\s*(억|천만|백만|만|천)?\s*원")

_UNIT_VALUE = {"억": 10**8, "천만": 10**7, "백만": 10**6, "만": 10**4, "천": 10**3, None: 1}


def _to_value(number_text, unit):
    number = float(number_text.replace(",", ""))
    return int(number * _UNIT_VALUE.get(unit, 1))


def humanize(value):
    if value is None:
        return None
    if value >= 10**8:
        eok = value // 10**8
        man = (value % 10**8) // 10**4
        if man:
            return f"{eok}억 {man:,}만원"
        return f"{eok}억원"
    if value >= 10**4:
        man = value / 10**4
        return f"{man:,.0f}만원"
    return f"{value:,}원"


def _amount_in(segment):
    match = _AMOUNT_RE.search(segment)
    if not match:
        return None, None
    value = _to_value(match.group(1), match.group(2))
    return value, match.group(0).strip()


def _count_in(segment):
    match = _COUNT_RE.search(segment)
    if match:
        return int(match.group(1))
    match = _PAREN_COUNT_RE.search(segment)
    if match:
        return int(match.group(1))
    return None


_RANK_PRIORITY = {
    "그랑프리": 0, "대상": 1, "1등": 1, "1위": 1,
    "금상": 2, "최우수상": 2, "최우수": 3,
    "은상": 4, "우수상": 4, "2등": 4, "2위": 4,
    "동상": 6, "장려상": 6, "장려": 7, "3등": 7, "3위": 7,
    "특별상": 8, "입선": 9, "가작": 9,
}


def _rank_key(label):
    for rank, priority in _RANK_PRIORITY.items():
        if rank in label:
            return priority
    return 99


def _is_section_header(line):
    if "시상" not in line or "이후" in line:
        return False
    if re.match(r"^(?:■|□|●|○|▶|·|•|-|\*)\s*시상", line):
        return True
    return bool(re.search(r"시상\s*(?:내역|내용|금|규모|계획|안내|상금|시상품)", line))


def _section_text(body_text):
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    start = None
    for index, line in enumerate(lines):
        if _is_section_header(line):
            start = index
            break
    if start is None:
        for index, line in enumerate(lines):
            if "시상" in line and "이후" not in line:
                start = index
                break
    if start is None:
        return " ".join(lines), lines

    collected = []
    for line in lines[start:start + 40]:
        if collected and _STOP_RE.match(line):
            break
        collected.append(line)
    return " ".join(collected), lines


def extract_prizes(body_text):
    if not body_text:
        return {"first": None, "breakdown": [], "total": None}

    section, lines = _section_text(body_text)
    section = " ".join(section.split())

    total = None
    total_match = _TOTAL_RE.search(section)
    if total_match:
        total = _to_value(total_match.group(1), total_match.group(2))

    matches = list(_RANK_RE.finditer(section))
    entries = []
    seen_labels = set()
    for index, match in enumerate(matches):
        label = match.group(0).strip()
        if match.group(1):
            label = f"{match.group(1)}위"
        end = matches[index + 1].start() if index + 1 < len(matches) else match.start() + 160
        segment = section[match.start():end]
        value, raw = _amount_in(segment)
        if value is None:
            continue
        count = _count_in(segment)
        key = (label, value)
        if key in seen_labels:
            continue
        seen_labels.add(key)
        entries.append({
            "label": label,
            "count": count,
            "amount": humanize(value),
            "amount_value": value,
            "raw": segment.strip()[:160],
        })

    first = None
    if entries:
        first = min(entries, key=lambda entry: _rank_key(entry["label"]))

    return {"first": first, "breakdown": entries, "total": total}
