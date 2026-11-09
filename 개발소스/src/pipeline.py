import hashlib
import json
import random
import re
from datetime import datetime, timedelta

from requests.exceptions import RequestException

from .collectors.wevity import WevityClient
from .config import resolve
from .extractors.prize import extract_prizes, humanize
from .extractors.sections import extract_fields
from .extractors.summary import summarize
from .reporters import html_report
from .schedule import PRIORITY_DAYS, STATUS_LABELS, now_kst, schedule_bounds, schedule_status
from .storage import db

POLICY_ORDER = ["must", "allowed", "unclear", "prohibited"]
ANALYSIS_FIELDS = ("ai_policy", "ai_modality", "ai_evidence", "source_level", "confidence", "fit_score")
SUMMARY_FIELDS = ("sum_task", "sum_topic", "sum_format", "sum_target", "sum_submit", "sum_notes")
ENRICHMENT_FIELDS = (
    "prize_total_amount", "prize_first_label", "prize_first_count", "prize_first_amount",
    "prize_breakdown", "summary", *SUMMARY_FIELDS,
)
ACTIVE_LIST_MODES = {"ing", "future", "soon", "new"}


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
    return now_kst().isoformat(timespec="seconds")


def refresh_statuses(connection, now):
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        changes = []
        for row in db.get_contests(connection):
            status = schedule_status(*schedule_bounds(row), now)
            label = STATUS_LABELS[status]
            if (status, label) != (row["status"], row["status_label"]):
                changes.append((status, label, row["ix"]))
        connection.executemany("UPDATE contests SET status=?, status_label=? WHERE ix=?", changes)


def run_collect(config, client, connection, modes=None, categories=None, max_pages=None):
    collect_config = config["collect"]
    modes = modes or collect_config["modes"]
    categories = categories or collect_config["categories"]
    max_pages = max_pages or config["wevity"]["max_pages"]

    seen = set()
    collected_at = _now()
    for mode in modes:
        for category in categories:
            cidx = str(category.get("cidx", ""))
            for row in client.iter_list(mode, cidx, max_pages=max_pages):
                if row["ix"] in seen:
                    continue
                row["listing_status"] = row.pop("status", mode)
                row.pop("status_label", None)
                row["collected_at"] = collected_at
                db.upsert_contest(connection, row)
                seen.add(row["ix"])
    refresh_statuses(connection, now_kst())
    return len(seen)


def _analysis_revision(row):
    fields = [(row.get(key) or "").split() for key in ("body_text", "eligibility", "homepage_url")]
    attachments = row.get("attachments")
    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except ValueError:
            pass
    fields.append(attachments or [])
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()


def _detail_priority(row, now, refetch):
    start, end = schedule_bounds(row)
    status = schedule_status(start, end, now)
    listed = row.get("listing_status") in ACTIVE_LIST_MODES
    last_fetch = row.get("detail_fetched_at")
    seen_since_fetch = listed and (row.get("collected_at") or "") > (last_fetch or "")
    missing_body = not (row.get("body_text") or "").strip()
    if status == "end" and not (seen_since_fetch or refetch):
        return None
    next_week = now.date() + timedelta(days=PRIORITY_DAYS)
    near = (status == "ing" and end.date() <= next_week) or (
        status == "future" and start.date() <= next_week
    )
    if not (refetch or missing_body):
        if not (near or seen_since_fetch and status in {"end", "unknown"}):
            return None
        if last_fetch and datetime.fromisoformat(last_fetch) > now - timedelta(days=1):
            return None
    relevant_date = start if status == "future" else end
    return (not (missing_body or status == "end"), not near,
            relevant_date or now + timedelta(days=PRIORITY_DAYS + 1), -row["ix"])


def run_fetch_details(config, client, connection, limit=None, refetch=False, on_error=None):
    now = now_kst()
    queued = []
    for row in db.get_contests(connection):
        priority = _detail_priority(row, now, refetch)
        if priority is not None:
            queued.append((priority, row["ix"]))
    queued.sort()

    fetched = 0
    for _, ix in queued[:limit]:
        try:
            detail = client.fetch_detail(ix)
        except RequestException as error:
            if on_error:
                on_error(f"상세 수집 실패 ({ix}): {error}")
            continue
        if not (detail.get("body_text") or "").strip():
            if on_error:
                on_error(f"상세 수집 실패 ({ix}): 본문 없음. 다음 갱신에서 재시도합니다.")
            continue
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = dict(connection.execute("SELECT * FROM contests WHERE ix=?", (ix,)).fetchone())
            updated = {**previous, **detail}
            if _analysis_revision(updated) != _analysis_revision(previous):
                detail.update(dict.fromkeys((*ANALYSIS_FIELDS, "analyzed_at")))
            if any((updated.get(key) or "").split() != (previous.get(key) or "").split()
                   for key in ("body_text", "eligibility")):
                detail.update(dict.fromkeys(ENRICHMENT_FIELDS))
            detail["detail_fetched_at"] = _now()
            db.upsert_contest(connection, detail, commit=False)
        fetched += 1
    refresh_statuses(connection, now_kst())
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


def _validated_labels(connection, labels, batch):
    items = batch.get("items") if isinstance(batch, dict) else None
    if not isinstance(items, list) or not items or any(
        not isinstance(item, dict) or type(item.get("ix")) is not int or not item.get("analysis_revision")
        for item in items
    ):
        raise ValueError("판정 배치에 공고 ID 또는 본문 확인 정보가 없습니다.")
    expected = {item["ix"]: item["analysis_revision"] for item in items}
    if len(expected) != len(items):
        raise ValueError("판정 배치에 중복 공고가 있습니다.")
    if not isinstance(labels, list) or any(
        not isinstance(item, dict) or type(item.get("ix")) is not int for item in labels
    ):
        raise ValueError("판정 결과는 정수 ix가 포함된 JSON 배열이어야 합니다.")
    received = {item["ix"] for item in labels}
    if len(received) != len(labels) or received != expected.keys():
        raise ValueError("판정 결과의 공고 ID가 배치와 일치하지 않습니다. 누락·중복·추가 항목을 확인하세요.")

    for item in labels:
        ix = item["ix"]
        if item.get("ai_policy") not in POLICY_ORDER or item.get("source_level") not in ("L0", "L1", "L2", "L3"):
            raise ValueError(f"공고 {ix}의 AI 판정 또는 출처 등급이 올바르지 않습니다.")
        evidence = item.get("ai_evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"공고 {ix}의 판정 근거가 비어 있습니다.")
        modalities = item.get("ai_modality")
        if not isinstance(modalities, str) or (modalities.strip() and any(
            part.strip() not in {"video", "image", "text", "audio", "software"}
            for part in modalities.split(",")
        )):
            raise ValueError(f"공고 {ix}의 AI 형식이 올바르지 않습니다.")
        for key, maximum in (("confidence", 1), ("fit_score", 100)):
            value = item.get(key)
            if type(value) not in (int, float) or not 0 <= value <= maximum:
                raise ValueError(f"공고 {ix}의 {key} 값이 범위를 벗어났습니다.")
        current = connection.execute("SELECT * FROM contests WHERE ix=?", (ix,)).fetchone()
        if current is None or _analysis_revision(dict(current)) != expected[ix]:
            raise ValueError(f"공고 {ix}의 본문 또는 참가 조건이 바뀌었습니다. 새 배치로 다시 판정하세요.")


def run_apply(config, connection, labels_path, *, batch=None):
    with open(labels_path, encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    if batch is None and isinstance(payload, dict):
        labels = payload.get("labels") or payload.get("items") or []
    else:
        labels = payload

    now = _now()
    applied = 0
    with connection:
        if batch is not None:
            connection.execute("BEGIN IMMEDIATE")
            _validated_labels(connection, labels, batch)
        for item in labels:
            if "ix" not in item:
                continue
            record = {"ix": item["ix"], "analyzed_at": now}
            for key in (*ANALYSIS_FIELDS, *SUMMARY_FIELDS):
                if key in item:
                    record[key] = item[key]
            if isinstance(record.get("ai_modality"), (list, tuple)):
                record["ai_modality"] = ", ".join(record["ai_modality"])
            db.upsert_contest(connection, record, commit=False)
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


def analysis_queue(connection, *, keywords=None, scope="all", now=None):
    now = now if now is not None else now_kst()
    next_week = now.date() + timedelta(days=PRIORITY_DAYS)
    lowered = [keyword.lower() for keyword in keywords or []]
    pending = []
    detail_pending = 0
    for row in db.get_contests(connection, where="analyzed_at IS NULL OR analyzed_at=''"):
        start, end = schedule_bounds(row)
        status = schedule_status(start, end, now)
        if status == "end":
            continue
        if not (row.get("body_text") or "").strip():
            detail_pending += 1
            continue
        if status == "unknown" or not _matches_scope(row, scope):
            continue
        text = f"{row.get('title') or ''} {row['body_text']}"
        if lowered and not any(keyword in text.lower() for keyword in lowered):
            continue

        relevant_date = end if status == "ing" else start
        within_week = relevant_date.date() <= next_week
        tier = 0 if status == "ing" and within_week else 1
        if status == "future" and not within_week:
            tier = 2
        creative_or_ai = _matches_scope(row, "either")
        priority = (tier, tier != 0 and not creative_or_ai, relevant_date, -row["ix"])
        row["status"] = status
        pending.append((priority, row))
    pending.sort(key=lambda item: item[0])
    return [row for _, row in pending], detail_pending


def run_batch(config, connection, n=15, out_name=None, keywords=None, scope="all"):
    pending, detail_pending = analysis_queue(connection, keywords=keywords, scope=scope)

    picked = pending[:n]
    payload = {
        "generated_at": _now(),
        "pending_total": len(pending),
        "detail_pending": detail_pending,
        "count": len(picked),
        "items": [
            {
                "ix": row["ix"],
                "title": row["title"],
                "category": row["category"],
                "host": row["host"],
                "status": row["status"],
                "dday": row["dday"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "eligibility": row["eligibility"],
                "prize_total": row["prize_total"],
                "prize_first": row["prize_first"],
                "homepage_url": row["homepage_url"],
                "detail_url": row["detail_url"],
                "body_text": row["body_text"],
                "analysis_revision": _analysis_revision(row),
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
