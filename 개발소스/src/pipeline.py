import json
import random
import re
from datetime import datetime

from .collectors.wevity import BASE_URL, MODE_LABELS, WevityClient
from .config import resolve
from .extractors.prize import extract_prizes, humanize
from .extractors.sections import extract_fields
from .extractors.summary import summarize
from .reporters import html_report
from .storage import db

POLICY_ORDER = ["must", "allowed", "unclear", "prohibited"]


def build_client(config):
    wevity = config["wevity"]
    http = wevity["http"]
    return WevityClient(
        user_agent=http["user_agent"],
        delay=http["delay_seconds"],
        timeout=http["timeout"],
        retries=http["retries"],
    )


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_collect(config, client, connection, modes=None, categories=None, max_pages=None):
    collect_config = config["collect"]
    modes = modes or collect_config["modes"]
    categories = categories or collect_config["categories"]
    max_pages = max_pages or config["wevity"]["max_pages"]

    seen = 0
    for mode in modes:
        for category in categories:
            cidx = str(category.get("cidx", ""))
            for row in client.iter_list(mode, cidx, max_pages=max_pages):
                row["collected_at"] = _now()
                db.upsert_contest(connection, row)
                seen += 1
    return seen


def run_fetch_details(config, client, connection, limit=None, refetch=False):
    where = None if refetch else "body_text IS NULL"
    rows = db.get_contests(connection, where=where, order="ix DESC")
    if limit:
        rows = rows[:limit]

    fetched = 0
    for row in rows:
        detail = client.fetch_detail(row["ix"])
        detail.setdefault("status", row.get("status"))
        detail.setdefault("collected_at", row.get("collected_at") or _now())
        db.upsert_contest(connection, detail)
        fetched += 1
    return fetched


def run_extract_prizes(config, connection, refetch=False):
    where = None if refetch else "body_text IS NOT NULL AND (prize_breakdown IS NULL OR summary IS NULL)"
    rows = db.get_contests(connection, where=where)
    done = 0
    for row in rows:
        result = extract_prizes(row.get("body_text"))
        record = {"ix": row["ix"], "prize_breakdown": result["breakdown"]}
        summary = summarize(row.get("body_text"), row.get("title"))
        if summary:
            record["summary"] = summary
        fields = extract_fields(row.get("body_text"), row.get("eligibility"))
        record["sum_task"] = fields["task"]
        record["sum_topic"] = fields["topic"]
        record["sum_format"] = fields["format"]
        record["sum_target"] = fields["target"]
        record["sum_submit"] = fields["submit"]
        record["sum_notes"] = fields["notes"]
        if result["total"] is not None:
            record["prize_total_amount"] = humanize(result["total"])
        first = result["first"]
        if first:
            record["prize_first_label"] = first["label"]
            record["prize_first_count"] = first["count"]
            record["prize_first_amount"] = first["amount"]
        elif row.get("prize_first"):
            record["prize_first_amount"] = row["prize_first"]
            record["prize_first_label"] = "1등"
        db.upsert_contest(connection, record)
        done += 1
    return done


run_enrich = run_extract_prizes


def run_sample(config, connection, n=10, seed=None, out_name=None, only_unanalyzed=False):
    rows = db.get_contests(connection)
    if only_unanalyzed:
        rows = [row for row in rows if not row.get("ai_policy")]

    rng = random.Random(seed)
    picked = rng.sample(rows, min(n, len(rows)))

    payload = {
        "generated_at": _now(),
        "count": len(picked),
        "items": [
            {
                "ix": row["ix"],
                "title": row["title"],
                "category": row["category"],
                "host": row["host"],
                "status": row["status"],
                "dday": row["dday"],
                "end_date": row["end_date"],
                "prize_total": row["prize_total"],
                "homepage_url": row["homepage_url"],
                "detail_url": row["detail_url"],
                "body_text": row["body_text"],
            }
            for row in picked
        ],
    }

    export_dir = resolve(config["storage"]["export_dir"])
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (out_name or f"sample_{len(picked)}.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return target


def run_apply(config, connection, labels_path):
    with open(labels_path, encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        labels = payload.get("labels") or payload.get("items") or []
    else:
        labels = payload

    now = _now()
    applied = 0
    for item in labels:
        if "ix" not in item:
            continue
        record = {"ix": item["ix"], "analyzed_at": now}
        for key in ("ai_policy", "ai_modality", "ai_evidence",
                    "source_level", "confidence", "fit_score",
                    "sum_task", "sum_topic", "sum_format",
                    "sum_target", "sum_submit", "sum_notes"):
            if key in item:
                record[key] = item[key]
        if isinstance(record.get("ai_modality"), (list, tuple)):
            record["ai_modality"] = ", ".join(record["ai_modality"])
        db.upsert_contest(connection, record)
        applied += 1
    return applied


AI_KEYWORD_RE = re.compile(
    r"\bAI\b|인공지능|생성형|프롬프트|챗GPT|ChatGPT|Suno|Midjourney|미드저니|Sora|Stable Diffusion",
    re.IGNORECASE,
)
CREATIVE_CATEGORIES = (
    "영상/ucc/사진", "디자인/캐릭터/웹툰", "예체능/미술/음악",
    "웹/모바일/it", "게임/소프트웨어",
)


def _matches_scope(row, scope):
    if scope in (None, "all"):
        return True
    text = f"{row.get('title') or ''} {row.get('body_text') or ''}"
    is_ai = bool(AI_KEYWORD_RE.search(text))
    category = (row.get("category") or "").lower()
    is_creative = any(name in category for name in CREATIVE_CATEGORIES)
    if scope == "ai":
        return is_ai
    if scope == "creative":
        return is_creative
    if scope == "either":
        return is_ai or is_creative
    return True


def run_batch(config, connection, n=15, out_name=None, keywords=None, scope="all"):
    rows = db.get_contests(connection, order="ix DESC")
    pending = [row for row in rows if not row.get("analyzed_at")]
    pending = [row for row in pending if _matches_scope(row, scope)]
    if keywords:
        lowered = [keyword.lower() for keyword in keywords]
        pending = [
            row for row in pending
            if any(
                keyword in ((row.get("title") or "") + " " + (row.get("body_text") or "")).lower()
                for keyword in lowered
            )
        ]

    picked = pending[:n]
    payload = {
        "generated_at": _now(),
        "pending_total": len(pending),
        "count": len(picked),
        "items": [
            {
                "ix": row["ix"],
                "title": row["title"],
                "category": row["category"],
                "host": row["host"],
                "status": row["status"],
                "dday": row["dday"],
                "end_date": row["end_date"],
                "eligibility": row["eligibility"],
                "prize_total": row["prize_total"],
                "prize_first": row["prize_first"],
                "homepage_url": row["homepage_url"],
                "detail_url": row["detail_url"],
                "body_text": row["body_text"],
            }
            for row in picked
        ],
    }

    export_dir = resolve(config["storage"]["export_dir"])
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (out_name or "batch.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return target, len(pending), len(picked)


def run_report(config, connection, out_name=None):
    rows = db.get_contests(connection)
    groups = {policy: [] for policy in POLICY_ORDER}
    for row in rows:
        policy = row.get("ai_policy")
        if policy in groups:
            groups[policy].append(row)

    lines = ["# AI 공모전 판정 리포트", f"- 생성: {_now()}", f"- 분석 완료: {sum(len(v) for v in groups.values())}건", ""]
    titles = {"must": "AI 필수", "allowed": "AI 허용", "unclear": "확인 필요", "prohibited": "AI 금지"}
    for policy in POLICY_ORDER:
        items = groups[policy]
        lines.append(f"## {titles[policy]} ({len(items)})")
        if not items:
            lines.append("- (없음)")
        for row in items:
            modalities = row.get("ai_modality") or "-"
            evidence = (row.get("ai_evidence") or "").replace("\n", " ").strip()
            amount = row.get("prize_first_amount") or row.get("prize_first") or "-"
            label = row.get("prize_first_label") or "1등"
            count = row.get("prize_first_count")
            prize = f"{label} {count}명 · {amount}" if count else f"{label} · {amount}"
            lines.append(
                f"- [{row['title']}]({row['detail_url']}) | {row.get('dday') or row.get('end_date') or '-'}"
                f" | {modalities} | 상금 {prize}"
                + (f"\n  - 근거: {evidence}" if evidence else "")
            )
        lines.append("")

    export_dir = resolve(config["storage"]["export_dir"])
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (out_name or "report.md")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def run_html_report(config, connection, out_name=None):
    rows = db.get_contests(connection)
    html = html_report.render(rows, _now())
    export_dir = resolve(config["storage"]["export_dir"])
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / (out_name or "report.html")
    target.write_text(html, encoding="utf-8")
    return target


def run_export(config, connection, export_format="csv", out_path=None):
    if export_format != "csv":
        raise ValueError(f"unsupported export format: {export_format}")
    export_dir = resolve(config["storage"]["export_dir"])
    target = export_dir / (out_path or "contests.csv")
    return db.export_csv(connection, target)


def run_bookmark(config, connection, ixs=None, remove=False, out_name=None):
    if not ixs:
        rows = db.get_bookmarks(connection)
        lines = ["ix,title,end_date,ai_policy,detail_url"]
        for row in rows:
            title = (row.get("title") or "").replace(",", " ")
            lines.append(f"{row['ix']},{title},{row.get('end_date') or ''},{row.get('ai_policy') or ''},{row.get('detail_url') or ''}")
        export_dir = resolve(config["storage"]["export_dir"])
        export_dir.mkdir(parents=True, exist_ok=True)
        target = export_dir / (out_name or "bookmarks.csv")
        target.write_text("\n".join(lines), encoding="utf-8-sig")
        return target, len(rows)

    changed = 0
    for ix in ixs:
        changed += db.set_bookmark(connection, ix, 0 if remove else 1)
    return None, changed


def run_serve(config, connection, port=8765):
    import http.server
    import json as _json
    import threading

    db_path = resolve(config["storage"]["db_path"])
    export_dir = resolve(config["storage"]["export_dir"])
    html_path = export_dir / "report.html"
    if not html_path.exists():
        run_html_report(config, connection)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send_json(self, payload, status=200):
            body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/api/bookmarks"):
                conn = db.connect(db_path)
                try:
                    self._send_json({"bookmarks": db.list_bookmark_ids(conn)})
                finally:
                    conn.close()
                return
            if self.path in ("/", "/index.html", "/report.html"):
                body = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self):
            if not self.path.startswith("/api/bookmark"):
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = _json.loads(self.rfile.read(length) or b"{}")
                ix = int(data.get("ix"))
                value = 1 if data.get("value") else 0
            except (ValueError, TypeError):
                self._send_json({"error": "invalid payload"}, 400)
                return
            conn = db.connect(db_path)
            try:
                db.set_bookmark(conn, ix, value)
                self._send_json({"ix": ix, "bookmarked": value})
            finally:
                conn.close()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"
