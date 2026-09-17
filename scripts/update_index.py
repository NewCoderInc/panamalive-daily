#!/usr/bin/env python3
"""
Point docs/index.html at the newest day, so there is one URL to bookmark.

    python3 update_index.py --docs docs

A redirect rather than a copy: the day pages keep their own URLs, so an older
one can still be opened directly if a post needs redoing.
"""
import argparse, pathlib, re, sys

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    a = ap.parse_args()
    root = pathlib.Path(a.docs)
    days = sorted(p.name for p in root.iterdir()
                  if p.is_dir() and DAY.match(p.name)
                  and (p / "index.html").exists())
    if not days:
        print("no day pages yet - leaving index alone")
        return 0
    latest = days[-1]
    (root / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        '<meta http-equiv="refresh" content="0; url=./%s/">'
        "<title>Today's post</title></head><body>"
        '<p>Opening <a href="./%s/">%s</a>&hellip;</p></body></html>'
        % (latest, latest, latest), encoding="utf-8")
    print("docs/index.html -> %s  (%d day page(s) kept)" % (latest, len(days)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
