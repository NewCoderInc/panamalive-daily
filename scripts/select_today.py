#!/usr/bin/env python3
"""
Slice the week's events.json down to one day's Instagram carousel.

    python3 select_today.py events.json --date 2026-09-09 --out today.json

Deliberately dumb. Every editorial judgement -- is this time real, is this
venue the venue, is this price the whole ladder -- already happened when
events.json was built by the pty-week pass. This script only chooses which of
that day's rows fit in ten slides, and in what order. It invents nothing and
it never guesses a missing field.

Ordering follows the site's CAT_PRIORITY so the carousel reads like the page:
Live Music, then Festivals and Concerts, then Sport, then everything else.
Within a tier, an event with a confirmed start time outranks one without,
because a slide that cannot say when is a weaker slide.
"""
import argparse, datetime as dt, json, pathlib, sys
from collections import Counter

CAT_PRIORITY = ["Live Music", "Festivals and Concerts", "Sport"]
# Cover + events + closing CTA must stay <= 10 (Instagram's carousel ceiling).
MAX_EVENT_SLIDES = 8


def cat_rank(c):
    try:
        return CAT_PRIORITY.index(c or "")
    except ValueError:
        return len(CAT_PRIORITY)


def sort_key(e, counts):
    """Mirrors the page's own order: the three priority categories, then the
    rest by how many events that category has today -- the site's
    "everything else by count" rule. Keeping the two surfaces in the same
    order is the point; a carousel that ranks the day differently from the
    page it links to reads as a different editor."""
    has_time = 0 if (e.get("time") or "").strip() else 1
    beyond = 1 if e.get("beyond") else 0          # in-city first
    return (beyond, cat_rank(e.get("cat")), -counts.get(e.get("cat"), 0),
            has_time, e.get("time") or "99:99", (e.get("title") or "").lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD, the day to post")
    ap.add_argument("--out", default="today.json")
    ap.add_argument("--max", type=int, default=MAX_EVENT_SLIDES)
    a = ap.parse_args()

    day = dt.date.fromisoformat(a.date)
    rows = json.loads(pathlib.Path(a.events).read_text(encoding="utf-8"))
    todays = [e for e in rows if (e.get("date") or "") == a.date]

    if not todays:
        # A genuinely empty day is a real answer, not a failure -- but it is
        # never worth a post, so signal it and let the runner skip cleanly.
        pathlib.Path(a.out).write_text(json.dumps(
            {"date": a.date, "total": 0, "shown": [], "overflow": 0},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("0 events on %s -- nothing to post" % a.date)
        return 3

    counts = Counter(e.get("cat") for e in todays)
    todays.sort(key=lambda e: sort_key(e, counts))
    shown, overflow = todays[:a.max], max(0, len(todays) - a.max)

    payload = {
        "date": a.date,
        "weekday": day.strftime("%A"),
        "pretty": "%s %d" % (day.strftime("%B"), day.day),
        "total": len(todays),
        "overflow": overflow,
        "shown": shown,
    }
    pathlib.Path(a.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("wrote %s" % a.out)
    print("  %s -- %d event(s) today, %d on slides, %d in the '+more' line"
          % (a.date, len(todays), len(shown), overflow))
    for e in shown:
        print("    %-6s %-22s %s" % (e.get("time") or "--",
                                     (e.get("cat") or "?")[:22],
                                     (e.get("title") or "")[:46]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
