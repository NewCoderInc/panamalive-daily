#!/usr/bin/env python3
"""
Read the week's events straight from the live panamalive.ai page.

    python3 fetch_site_events.py --out events.json --tx-out tx.json
    python3 fetch_site_events.py --html saved-page.html --out events.json

The site is the source of truth: the weekly pty-week build bakes its rows into
the page as `const EVENTS = [...]` (plus `BEYOND` for trips outside the city)
and its translations as `const TX = {...}`. Reading them here means the daily
post can never drift from what the site shows, and there is no hand-copied
events.json to go stale.

Field names are mapped to the ones the daily scripts already use
(d -> date, t -> time, addr -> address). Nothing is invented: a missing time
stays missing and an em-dash price becomes no price.

Exit codes: 0 ok, 1 could not fetch or parse (the workflow then falls back to
the committed events.json). Output files are written only on full success.
"""
import argparse, json, pathlib, re, sys, urllib.request

URL = "https://panamalive.ai/"
UA = "panamalive-daily/1.0 (+https://github.com/NewCoderInc/panamalive-daily)"
NONE_MARKS = {"", "—", "-", "–", "n/a", "tba"}


def grab(html, name):
    """Decode the JSON literal assigned to `const NAME =` in the page."""
    m = re.search(r"(?:const|let|var)\s+%s\s*=\s*" % re.escape(name), html)
    if not m:
        return None
    value, _ = json.JSONDecoder().raw_decode(html, m.end())
    return value


def clean(s):
    s = (s or "").strip() if isinstance(s, str) else s
    return None if isinstance(s, str) and s.lower() in NONE_MARKS else s


def row(e, beyond=False):
    out = {
        "date": e.get("d") or e.get("date"),
        "time": clean(e.get("t") or e.get("time")),
        "title": clean(e.get("title")),
        "venue": clean(e.get("venue")),
        "address": clean(e.get("addr") or e.get("address") or e.get("where")),
        "cat": clean(e.get("cat")),
        "price": clean(e.get("price")),
        "pick": bool(e.get("pick")),
        "free": bool(e.get("free")),
        "desc": clean(e.get("desc")),
        "note": clean(e.get("note")),
        "src": clean(e.get("src")) or "PanamaLive.Ai",
        "url": clean(e.get("url")),
        "beyond": beyond,
    }
    # The site lists standing attractions (museums, the Canal) every day as
    # "<place> — visita". They are real but not *today's* news, so they are
    # marked evergreen and rank below dated events in select_today.py.
    if re.search(r"[—-]\s*visita\s*$", out["title"] or "", re.I):
        out["evergreen"] = True
    if out["free"] and not out["price"]:
        out["price"] = "Free"
    return {k: v for k, v in out.items() if v not in (None, "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--html", help="read a saved copy of the page instead")
    ap.add_argument("--out", default="events.json")
    ap.add_argument("--tx-out", default="tx.json")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args()

    try:
        if a.html:
            html = pathlib.Path(a.html).read_text(encoding="utf-8")
        else:
            req = urllib.request.Request(a.url, headers={"User-Agent": UA,
                                                         "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=a.timeout) as r:
                html = r.read().decode("utf-8", "replace")
    except Exception as ex:                               # network, 4xx/5xx
        print("fetch failed: %s" % ex, file=sys.stderr)
        return 1

    try:
        events = grab(html, "EVENTS")
        beyond = grab(html, "BEYOND") or []
        tx = grab(html, "TX") or {}
    except ValueError as ex:
        print("page template changed - could not parse: %s" % ex, file=sys.stderr)
        return 1
    if not isinstance(events, list) or not events:
        print("no EVENTS array found on the page", file=sys.stderr)
        return 1

    # BEYOND lists the trips outside the city. The page usually repeats them
    # in EVENTS too; then the EVENTS row (which has the time and category) is
    # kept and flagged beyond, and only BEYOND-only trips are added.
    key = lambda e: (e.get("d") or e.get("date"), (e.get("title") or "").strip().lower())
    far = {key(e) for e in beyond}
    rows = [row(e, beyond=key(e) in far) for e in events]
    have = {key(e) for e in events}
    rows += [row(e, beyond=True) for e in beyond if key(e) not in have]
    rows = [r for r in rows if r.get("date") and r.get("title")]
    rows.sort(key=lambda r: (r["date"], r.get("beyond", False), r.get("time") or "99"))

    pathlib.Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    pathlib.Path(a.tx_out).write_text(json.dumps(tx, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    days = sorted({r["date"] for r in rows})
    n_far = sum(1 for r in rows if r.get("beyond"))
    print("wrote %s: %d events (%d outside the city) across %s .. %s"
          % (a.out, len(rows), n_far, days[0], days[-1]))
    print("wrote %s: %d translations" % (a.tx_out, len(tx)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
