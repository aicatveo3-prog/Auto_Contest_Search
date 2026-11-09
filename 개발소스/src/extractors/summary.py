import re

_SUBJECT_KEYS = [
    "공모주제", "공모 주제", "응모주제", "응모 주제", "작품주제", "작품 주제",
    "공모내용", "공모 내용", "공모분야", "공모 분야", "공모품목", "공모품목",
    "사업목적", "사업 목적", "심사기준", "주제", "목적", "내용", "개요",
]

_NOISE_RE = re.compile(
    r"^(?:문의|접수|제출|발표|일정|심사|주최|주관|후원|기간|시상|유의)"
)
_ELIG_RE = re.compile(
    r"(재학|휴학|졸업|자격|참가자|응모자|모집|신청|거주|만\s*\d+|누구나|"
    r"대상\s*[:：]|참가비|출품료|참여\s*가?능|구성|팀으로|명\s*이내|인\s*이내)"
)
_MONEY_RE = re.compile(r"\d[\d,]*\s*(?:억|천만|백만|만|천)?\s*원")
_HEADER_RE = re.compile(r"^[【\[（(][^】\]）)]{1,30}[】\]）)]$")
_DATE_RE = re.compile(r"\d{2,4}\s*[.\-/년]\s*\d{1,2}")
_PARTICLE_PREFIX = ("를 ", "을 ", "이 ", "가 ", "은 ", "는 ", "의 ", "에 ", "로 ", "과 ", "와 ")


def _clean(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[■□●○▶▷·•\-\*\d\.\)\s]+", "", text).strip()
    text = text.strip(" -·•")
    if len(text) > 160:
        text = text[:159].rstrip() + "…"
    return text


def _looks_like_content(text):
    if len(text) < 10:
        return False
    if _NOISE_RE.match(text) or _ELIG_RE.search(text):
        return False
    if _MONEY_RE.search(text) or "상금" in text:
        return False
    if _HEADER_RE.match(text) or text.endswith("부문】"):
        return False
    if text.startswith(_PARTICLE_PREFIX):
        return False
    if _DATE_RE.search(text) and len(text) < 25:
        return False
    return True


def summarize(body_text, title=None):
    if not body_text:
        return None
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    if not lines:
        return None

    if title:
        title_clean = _clean(title)
        while lines and (_clean(lines[0]) == title_clean or title_clean.startswith(_clean(lines[0]))):
            lines = lines[1:]
    if not lines:
        return None

    for index, line in enumerate(lines):
        for key in _SUBJECT_KEYS:
            if key not in line:
                continue
            remainder = line.split(key, 1)[1].lstrip(" :：-•·>").strip()
            if len(remainder) >= 8 and _looks_like_content(_clean(remainder)):
                return _clean(remainder)
            if index + 1 < len(lines):
                candidate = _clean(lines[index + 1])
                if _looks_like_content(candidate):
                    return candidate

    for line in lines[:12]:
        candidate = _clean(line)
        if _looks_like_content(candidate):
            return candidate
    return None
