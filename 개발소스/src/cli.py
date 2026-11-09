import argparse
import sys
import time

from .config import load_settings, resolve
from .pipeline import (
    build_client,
    run_apply,
    run_batch,
    run_bookmark,
    run_collect,
    run_enrich,
    run_export,
    run_extract_prizes,
    run_fetch_details,
    run_html_report,
    run_report,
    run_sample,
    run_serve,
)
from .storage import db


def _parse_list(value):
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _print(message):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(message)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="contest-finder")
    parser.add_argument("--settings", default=None, help="path to settings.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    collect_parser = sub.add_parser("collect", help="collect contest lists")
    collect_parser.add_argument("--modes", default=None, help="comma list, e.g. ing,future")
    collect_parser.add_argument("--cats", default=None, help="comma list of cidx, e.g. 10,20")
    collect_parser.add_argument("--pages", type=int, default=None, help="limit pages per mode/category")

    fetch_parser = sub.add_parser("fetch", help="fetch detail pages")
    fetch_parser.add_argument("--limit", type=int, default=None)
    fetch_parser.add_argument("--refetch", action="store_true")

    prizes_parser = sub.add_parser("prizes", help="extract structured prize info from bodies")
    prizes_parser.add_argument("--refetch", action="store_true")

    enrich_parser = sub.add_parser("enrich", help="extract prizes + summary from bodies")
    enrich_parser.add_argument("--refetch", action="store_true")

    sample_parser = sub.add_parser("sample", help="export random contests for analysis")
    sample_parser.add_argument("--n", type=int, default=10)
    sample_parser.add_argument("--seed", type=int, default=None)
    sample_parser.add_argument("--out", default=None)
    sample_parser.add_argument("--only-unanalyzed", action="store_true")

    apply_parser = sub.add_parser("apply", help="apply analysis labels from JSON")
    apply_parser.add_argument("path")

    batch_parser = sub.add_parser("batch", help="export next unanalyzed batch")
    batch_parser.add_argument("--n", type=int, default=15)
    batch_parser.add_argument("--out", default=None)
    batch_parser.add_argument("--scope", default="all", choices=["all", "ai", "creative", "either"])
    batch_parser.add_argument("--keywords", default=None, help="comma list to filter")

    report_parser = sub.add_parser("report", help="write markdown report by ai_policy")
    report_parser.add_argument("--out", default=None)

    bookmark_parser = sub.add_parser("bookmark", help="manage bookmarked contests")
    bookmark_parser.add_argument("ix", nargs="*", type=int, help="ix numbers to bookmark")
    bookmark_parser.add_argument("--remove", action="store_true")
    bookmark_parser.add_argument("--list", action="store_true", help="export bookmarks to CSV")
    bookmark_parser.add_argument("--out", default=None)

    serve_parser = sub.add_parser("serve", help="serve dashboard with bookmark save API")
    serve_parser.add_argument("--port", type=int, default=8765)

    html_parser = sub.add_parser("html", help="write static HTML dashboard")
    html_parser.add_argument("--out", default=None)

    export_parser = sub.add_parser("export", help="export collected data")
    export_parser.add_argument("--format", default="csv")
    export_parser.add_argument("--out", default=None)

    sub.add_parser("stats", help="show collection statistics")

    args = parser.parse_args(argv)
    config = load_settings(args.settings)
    connection = db.connect(resolve(config["storage"]["db_path"]))
    db.init_db(connection)
    client = build_client(config)

    if args.command == "collect":
        modes = _parse_list(args.modes)
        categories = None
        if args.cats:
            categories = [{"name": cidx, "cidx": cidx} for cidx in _parse_list(args.cats)]
        count = run_collect(
            config, client, connection, modes=modes, categories=categories, max_pages=args.pages
        )
        _print(f"collected {count} list entries; total in db: {db.count(connection)}")

    elif args.command == "fetch":
        count = run_fetch_details(
            config, client, connection, limit=args.limit, refetch=args.refetch
        )
        _print(f"fetched {count} detail pages; total in db: {db.count(connection)}")

    elif args.command == "prizes":
        count = run_extract_prizes(config, connection, refetch=args.refetch)
        _print(f"extracted prizes for {count} contests")

    elif args.command == "enrich":
        count = run_enrich(config, connection, refetch=args.refetch)
        _print(f"enriched {count} contests")

    elif args.command == "sample":
        path = run_sample(
            config, connection, n=args.n, seed=args.seed,
            out_name=args.out, only_unanalyzed=args.only_unanalyzed,
        )
        _print(f"sample written to {path}")

    elif args.command == "apply":
        count = run_apply(config, connection, args.path)
        _print(f"applied {count} labels")

    elif args.command == "batch":
        keywords = _parse_list(args.keywords)
        path, pending, count = run_batch(
            config, connection, n=args.n, out_name=args.out,
            keywords=keywords, scope=args.scope,
        )
        _print(f"batch written to {path} ({count} items, pending {pending})")

    elif args.command == "report":
        path = run_report(config, connection, out_name=args.out)
        _print(f"report written to {path}")

    elif args.command == "bookmark":
        ixs = None if args.list else args.ix
        path, count = run_bookmark(
            config, connection, ixs=ixs, remove=args.remove, out_name=args.out
        )
        if path:
            _print(f"bookmarks ({count}) exported to {path}")
        else:
            _print(f"updated {count} contests")

    elif args.command == "serve":
        run_html_report(config, connection)
        server, url = run_serve(config, connection, port=args.port)
        _print(f"dashboard running at {url}  (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()

    elif args.command == "html":
        path = run_html_report(config, connection, out_name=args.out)
        _print(f"html dashboard written to {path}")

    elif args.command == "export":
        path = run_export(config, connection, export_format=args.format, out_path=args.out)
        _print(f"exported to {path}")

    elif args.command == "stats":
        total = db.count(connection)
        with_body = db.count(connection, "body_text IS NOT NULL")
        analyzed = db.count(connection, "ai_policy IS NOT NULL")
        rows = db.get_contests(connection, order="status")
        statuses = {}
        for row in rows:
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        _print(f"total: {total}")
        _print(f"with detail body: {with_body}")
        _print(f"analyzed (ai_policy): {analyzed}")
        _print(f"by status: {statuses}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
