import random
import re
import time

import requests
from bs4 import BeautifulSoup

from ..schedule import PERIOD_SEPARATOR

BASE_URL = "https://www.wevity.com/"

MODE_LABELS = {
    "ing": "접수중",
    "soon": "마감임박",
    "future": "접수예정",
    "new": "신규",
    "spec": "스페셜",
    "end": "마감",
}

_INFO_MAP = {
    "분야": "category",
    "응모대상": "eligibility",
    "주최/주관": "host",
    "후원/협찬": "sponsor",
    "총 상금": "prize_total",
    "1등 상금": "prize_first",
}


class WevityClient:
    def __init__(self, user_agent, delay=1.2, timeout=25, retries=3):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Referer": BASE_URL,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        })
        self.delay = delay
        self.timeout = timeout
        self.retries = retries

    def get(self, url, params=None):
        last_error = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"
                time.sleep(self.delay + random.uniform(0, 0.4))
                return response.text
            except requests.RequestException as error:
                last_error = error
                time.sleep(self.delay * (attempt + 1) * 2)
        raise last_error

    def list_params(self, mode, cidx, page):
        params = {"c": "find", "s": "1", "gub": "1", "gbn": "list", "gp": page}
        if mode:
            params["mode"] = mode
        if cidx:
            params["cidx"] = cidx
        return params

    def iter_list(self, mode, cidx="", max_pages=100):
        seen = set()
        for page in range(1, max_pages + 1):
            html = self.get(BASE_URL, params=self.list_params(mode, cidx, page))
            rows = self.parse_list(html)
            if not rows:
                break
            fresh = [row for row in rows if row["ix"] not in seen]
            if not fresh:
                break
            for row in fresh:
                seen.add(row["ix"])
                row["status"] = mode
                row["status_label"] = MODE_LABELS.get(mode, mode)
                yield row

    @staticmethod
    def parse_list(html):
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("div.ms-list ul.list")
        rows = []
        if not container:
            return rows
        for item in container.select("li"):
            anchor = item.select_one("div.tit > a")
            if not anchor:
                continue
            href = anchor.get("href", "")
            match = re.search(r"ix=(\d+)", href)
            if not match:
                continue

            flags = [badge.get_text(strip=True) for badge in anchor.select("span.stat")]
            for badge in anchor.select("span.stat"):
                badge.decompose()
            title = anchor.get_text(" ", strip=True)

            sub = item.select_one("div.sub-tit")
            category = ""
            if sub:
                category = re.sub(r"^분야\s*:\s*", "", sub.get_text(" ", strip=True)).strip()

            host_element = item.select_one("div.organ")
            host = host_element.get_text(" ", strip=True) if host_element else ""

            dday = ""
            day_element = item.select_one("div.day")
            if day_element:
                dday_match = re.search(r"D-\d+|D\+\d+", day_element.get_text(" ", strip=True))
                dday = dday_match.group(0) if dday_match else ""

            ix = int(match.group(1))
            rows.append({
                "ix": ix,
                "title": title,
                "category": category,
                "host": host,
                "dday": dday,
                "flags": ", ".join(flags) if flags else None,
                "detail_url": f"{BASE_URL}?c=find&s=1&gbn=view&gp=1&ix={ix}",
            })
        return rows

    def fetch_detail(self, ix):
        url = f"{BASE_URL}?c=find&s=1&gbn=view&gp=1&ix={ix}"
        html = self.get(url)
        return self.parse_detail(html, ix, url)

    @staticmethod
    def parse_detail(html, ix, url):
        soup = BeautifulSoup(html, "lxml")
        data = {"ix": ix, "detail_url": url}

        title_element = soup.select_one("div.tit-area h6.tit")
        if title_element:
            data["title"] = title_element.get_text(strip=True)

        info = {}
        homepage = None
        for item in soup.select("ul.cd-info-list > li"):
            label_element = item.select_one("span.tit")
            if not label_element:
                continue
            label = label_element.get_text(strip=True)
            if not label:
                continue

            anchor = item.select_one("a[href]")
            if anchor and label == "홈페이지":
                homepage = anchor.get("href")

            fragment = BeautifulSoup(str(item), "lxml")
            node = fragment.select_one("li")
            for label_node in node.select("span.tit"):
                label_node.decompose()
            dday_node = node.select_one("span.cil-dday")
            if dday_node:
                data["dday"] = dday_node.get_text(strip=True)
                dday_node.decompose()
            info[label] = node.get_text(" ", strip=True)

        for label, field in _INFO_MAP.items():
            if label in info:
                data[field] = info[label]

        if homepage:
            data["homepage_url"] = homepage

        duration = info.get("접수기간", "")
        if duration:
            start, *end = PERIOD_SEPARATOR.split(duration, maxsplit=1)
            data["start_date"] = start.strip()
            if end and end[0].strip():
                data["end_date"] = end[0].strip()

        attachment = info.get("첨부파일", "")
        data["attachments"] = [] if attachment in ("", "파일없음") else [attachment]

        body = soup.select_one("div#viewContents") or soup.select_one("div.comm-desc")
        if body:
            data["body_text"] = body.get_text("\n", strip=True)

        thumbnail = soup.select_one("div.img .thumb img")
        if thumbnail and thumbnail.get("src"):
            data["thumbnail"] = thumbnail["src"]

        return data
