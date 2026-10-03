#!/usr/bin/env python3
"""
Pull the current week's events straight off the live PanamaLive.Ai page.

    python3 fetch_site_events.py --out events.json --tx-out tx.json
    python3 fetch_site_events.py --html saved_page.html --out events.json   # offline

The weekly pty-week build embeds the whole week into the page as two JSON
literals -- `const EVENTS = [...]` and `const TX = {...}` -- written by
json.dumps, so they parse exactly. Reading them here means the daily post is
fed by the same data the website shows, with no hand-copied events.json to go
stale. That staleness is the whole reason this exists: a file holding only two
days made three consecutive midnight runs find nothing and skip silently.

It also does the cleanup that had to be done by hand every single day:

  * the same show listed twice at one venue and time (a ticket seller's entry
    and a festival's entry for one performance) is collapsed to one row,
    keeping whichever carries a published price;
  * one production running at two showtimes becomes one "6 & 8pm" row;
  * standing museum hours are flagged evergreen so they sort below the
    things that are actually on tonight;
  * anything the site marks as outside Panama City is flagged beyond.

It never invents a field. A price of "—" is the site saying "not published",
so it becomes no price at all, and the poster says TBA.
"""
import argparse, json, pathlib, re, sys, urllib.request

SITE = "https://panamalive.ai/"
BEYOND_RE = re.compile(r"Fuera de la ciudad de Panam|Outside Panama City", re.I)
EVERGREEN_RE = re.compile(r"\s[—-]\s*(visita|visit)\s*$", re.I)


def grab(src, name):
    """Return the JSON literal assigned by `const NAME = ...`, honouring strings
    so a bracket inside a title cannot end the match early."""
    i = src.find("const %s = " % name)
    if i < 0:
        return None
    j = src.index("=", i) + 1
    while src[j] in " \n\t\r":
        j += 1
    open_, close = src[j], ("]" if src[j] == "[" else "}")
    depth, in_str, esc = 0, False, False
    for k in range(j, len(src)):
        c = src[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return json.loads(src[j:k + 1])
    return None


def fmt12(t):
    hh, mm = (int(x) for x in t.split(":")[:2])
    return ("%d%s" % (hh % 12 or 12, "" if mm == 0 else ":%02d" % mm),
            "am" if hh < 12 else "pm")


def normalize(rows):
    out = []
    for r in rows:
        price = (r.get("price") or "").strip()
        note = (r.get("note") or "").strip()
        out.append({
            "date": r["d"],
            "time": r.get("t") or None,
            "title": (r.get("title") or "").strip(),
            "venue": (r.get("venue") or "").strip(),
            "address": (r.get("addr") or "").strip(),
            "cat": r.get("cat") or "Community",
            "price": None if price in ("", "—", "-") else price,
            "pick": bool(r.get("pick")),
            "note": note,
            "beyond": bool(r.get("_beyond")) or bool(BEYOND_RE.search(note)),
            "evergreen": bool(EVERGREEN_RE.search(r.get("title") or "")),
            "src": "PanamaLive.Ai",
        })

    # 1. One show, two listings: same day, same venue, same start time. Keep the
    #    one that publishes a price; on a tie, the longer (more descriptive)
    #    title, which is usually the festival's own programme entry.
    best = {}
    for e in out:
        if not e["time"]:
            best[id(e)] = e                     # no time -> cannot match safely
            continue
        k = (e["date"], e["venue"].lower(), e["time"])
        cur = best.get(k)
        if cur is None or (bool(e["price"]), len(e["title"])) > (bool(cur["price"]), len(cur["title"])):
            best[k] = e
    out = list(best.values())

    # 2. One production at several showtimes: same day, title and venue.
    groups = {}
    for e in out:
        groups.setdefault((e["date"], e["title"].lower(), e["venue"].lower()), []).append(e)
    merged = []
    for evs in groups.values():
        timed = sorted((e for e in evs if e["time"]), key=lambda e: e["time"])
        if len(timed) > 1:
            parts = [fmt12(e["time"]) for e in timed]
            same = all(p[1] == parts[0][1] for p in parts)
            label = (" & ".join(p[0] for p in parts) + parts[0][1] if same
                     else " & ".join(a + m for a, m in parts))
            first = dict(timed[0]); first["time"] = label
            merged.append(first)
            merged += [e for e in evs if not e["time"]]
        else:
            merged += evs
    merged.sort(key=lambda e: (e["date"], e["time"] or "99:99", e["title"]))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=SITE)
    ap.add_argument("--html", help="read a saved page instead of fetching")
    ap.add_argument("--out", default="events.json")
    ap.add_argument("--tx-out", default="tx.json")
    a = ap.parse_args()

    if a.html:
        src = pathlib.Path(a.html).read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(a.url, headers={"User-Agent": "panamalive-daily/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            src = r.read().decode("utf-8", "replace")

    rows, tx = grab(src, "EVENTS"), grab(src, "TX")
    if not rows:
        sys.exit("no EVENTS array found on %s -- has the page template changed?"
                 % (a.html or a.url))

    events = normalize(rows)
    pathlib.Path(a.out).write_text(json.dumps(events, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    if tx:
        pathlib.Path(a.tx_out).write_text(json.dumps(tx, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

    days = sorted({e["date"] for e in events})
    print("fetched %d rows -> %d after cleanup, %s .. %s, %d translations"
          % (len(rows), len(events), days[0], days[-1], len(tx or {})))
    for d in days:
        print("   %s  %3d" % (d, sum(e["date"] == d for e in events)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
