#!/usr/bin/env python3
"""
Turn the live site's Live Music listings into the week.json that ptymix.py
renders, plus the caption for the reel.

    python3 mix_week.py --date 2026-10-08 --out build/week.json --caption build/caption.txt
    python3 mix_week.py --html saved_page.html --date 2026-10-08 ...      # offline

It reads the same `const EVENTS` / `const TX` literals the daily post reads,
but keeps the raw rows: `verify` (the site's "something is unpublished or only
a weekly pattern" flag) decides what may be a headline, and the daily
normaliser drops it.

The editorial rules, which used to be applied by hand each week:

  * nothing dated before --date is shown -- a promo for a show that is over
    is worse than no promo;
  * a HEADLINE slide needs a row the site fully confirms (verify false). A
    row with a missing time or price, or one that is only a weekly pattern,
    is listed on its day slide and never headlined;
  * the genre label comes from words in the listing itself. When the listing
    names no genre the label is the neutral "Live music" -- never a guess;
  * a missing time is left blank and a missing price is left out. "TBA" is
    never printed;
  * every remaining listing appears on a day slide, so the reel is the whole
    week and not a selection.

Exit code 3 means "nothing to post" (the site's week does not cover --date, or
it has no live music from that day on). That is a skip, not a failure.
"""
import argparse, datetime as dt, json, pathlib, re, sys, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_site_events import grab, SITE  # noqa: E402

ACCENTS = ["#ff3b30", "#22d3ee", "#ff2e7e", "#b06cff", "#ffb020"]
MAX_FEATURES, MAX_DAY_ROWS, GROUP_ROWS = 6, 8, 2
HASHTAGS = "#pty #musicaenvivo #quehacerenpanama #panamacitypanama #PTYLiveMix"

# First match wins, so the specific sits above the general: "Queen rock
# anthems by candlelight" is a candlelight show, not a rock night.
GENRES = [
    (r"candlelight|a la luz de las velas", "Classical by candlelight", "candle"),
    (r"power metal", "Power metal", "metal"),
    (r"\bmetal\b", "Metal", "metal"),
    (r"\bpunk\b", "Punk rock", "punk"),
    (r"electr[oó]nic|techno|\bhouse\b|\bdj\b", "Electronic", "electro"),
    (r"\bjazz\b", "Jazz", "candle"),
    (r"cuarteto|quartet|sinf[oó]n|orquesta|orchestra|cl[aá]sic|classical", "Classical", "candle"),
    (r"t[ií]pic", "Típico", "vinyl"),
    (r"\bsalsa\b", "Salsa", "vinyl"),
    (r"reggaet[oó]n", "Reggaeton", "vinyl"),
    (r"\breggae\b", "Reggae", "vinyl"),
    (r"\bblues\b", "Blues", "vinyl"),
    (r"tribut", "Tribute", "punk"),
    (r"\brock\b", "Rock", "punk"),
    (r"cuban|\bbolero|\bson\b|latin", "Latin", "vinyl"),
]
DAY_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def d_(s):
    return dt.date.fromisoformat(s)


def short_date(s):
    d = d_(s)
    return "%s %s %d" % (DAY_EN[d.weekday()], MON[d.month - 1], d.day)


def span(a, b):
    a, b = d_(a), d_(b)
    if a == b:
        return "%s %d" % (MON[a.month - 1], a.day)
    if a.month == b.month:
        return "%s %d – %d" % (MON[a.month - 1], a.day, b.day)
    return "%s %d – %s %d" % (MON[a.month - 1], a.day, MON[b.month - 1], b.day)


def t12(t):
    """'20:00' -> '8:00 PM'. Anything that is not a clean 24h time is treated
    as unpublished rather than printed as-is."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", (t or "").strip())
    if not m:
        return ""
    hh, mm = int(m.group(1)), m.group(2)
    return "%d:%s %s" % (hh % 12 or 12, mm, "AM" if hh < 12 else "PM")


def price_line(en_price, free):
    p = (en_price or "").strip()
    if free or re.search(r"\bgratis\b|\bfree\b", p, re.I):
        return "Free entry"
    amounts = re.findall(r"\$\s?(\d+(?:\.\d{1,2})?)", p)
    if not amounts:
        return ""
    if len(amounts) > 1:
        # A price ladder never fits a slide; the floor is the honest summary.
        return "From $%s" % min(amounts, key=float)
    if len(p) <= 24:
        return p[0].upper() + p[1:]
    return "From $%s" % amounts[0]


def nice(s):
    """Titles arrive in whatever case the promoter typed. An all-caps name is
    brought down to title case for the caption; mixed case is left alone."""
    s = s.strip()
    return s.title() if s.isupper() and len(s) > 3 else s


def strip_venue(title, venue):
    m = re.search(r"\s+(?:at|en|@|—|–|-)\s+(.+)$", title)
    if m:
        tail, v = m.group(1).strip().lower(), venue.strip().lower()
        if v and (v.startswith(tail) or tail.startswith(v)):
            return title[:m.start()].strip()
    return title


def genre_of(row, en):
    text = " ".join([row.get("title") or "", en(row.get("title")),
                     row.get("desc") or "", en(row.get("desc"))]).lower()
    # A venue called "Rock & Folk" must not make an electronica night a rock
    # night, so venue names are removed before the words are read.
    v = (row.get("venue") or "").lower()
    if v:
        text = text.replace(v, " ")
        text = re.sub(re.escape(v).replace(r"\&", r"(?:&|and|y)"), " ", text)
    text = re.sub(r"rock\s*(?:&|and|y)\s*folk", " ", text)
    for pat, label, art in GENRES:
        if re.search(pat, text):
            return label, art
    return "Live music", "vinyl"


def first_sentence(s, title, limit=64):
    s = (s or "").strip()
    if not s:
        return ""
    s = re.sub(r"^%s\s*[:\-—–]\s*" % re.escape(title), "", s, flags=re.I)
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    if not m:
        return ""
    out = m.group(1).strip()
    letters = [c for c in out if c.isalpha()]
    if len(out) > limit or len(out) < 12 or not letters:
        return ""
    if sum(c.isupper() for c in letters) > 0.6 * len(letters):
        return ""                      # promoter shouting; not slide copy
    return out[0].upper() + out[1:]


def load(a):
    if a.html:
        src = pathlib.Path(a.html).read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(a.url, headers={"User-Agent": "panamalive-daily/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            src = r.read().decode("utf-8", "replace")
    rows, tx = grab(src, "EVENTS"), grab(src, "TX") or {}
    if not rows:
        sys.exit("no EVENTS array found on %s -- has the page template changed?"
                 % (a.html or a.url))
    return rows, tx


def build(rows, tx, today):
    def en(s):
        hit = tx.get(s or "")
        if isinstance(hit, dict):
            return hit.get("en") or s or ""
        return hit if isinstance(hit, str) else (s or "")

    week = sorted({r["d"] for r in rows})
    if today < week[0] or today > week[-1]:
        return None, "the site shows %s to %s, which does not include %s" % (week[0], week[-1], today)

    seen, lm = set(), []
    for r in rows:
        if r.get("cat") != "Live Music":
            continue
        k = (r["d"], r.get("t") or "", (r.get("title") or "").lower(), (r.get("venue") or "").lower())
        if k not in seen:
            seen.add(k)
            lm.append(r)
    total = len(lm)
    lm = [r for r in lm if r["d"] >= today]
    if not lm:
        return None, "no live music listed from %s onward" % today

    # A venue listed on five or more days is a nightly fixture, not a weekly one.
    nights = {}
    for r in rows:
        if r.get("cat") == "Live Music":
            nights.setdefault(((r.get("title") or "").lower(), (r.get("venue") or "").lower()), set()).add(r["d"])

    def pattern(r):
        if not r.get("verify"):
            return ""
        note = "%s %s" % (r.get("note") or "", en(r.get("note")))
        if len(nights.get(((r.get("title") or "").lower(), (r.get("venue") or "").lower()), ())) >= 5:
            return "nightly"
        return "weekly night" if re.search(r"patr[oó]n semanal|weekly pattern", note, re.I) else ""

    # ---- headline slides: fully confirmed rows only --------------------
    ok = sorted((r for r in lm if not r.get("verify") and t12(r.get("t"))),
                key=lambda r: (r["d"], r.get("t") or ""))
    groups, used = [], set()
    for r in ok:
        if id(r) in used:
            continue
        title = en(r.get("title"))
        mates = [r]
        if ":" in title:
            pre = title.split(":", 1)[0].strip().lower()
            mates = [x for x in ok if id(x) not in used and x["d"] == r["d"]
                     and x.get("venue") == r.get("venue")
                     and en(x.get("title")).split(":", 1)[0].strip().lower() == pre][:GROUP_ROWS]
        for x in mates:
            used.add(id(x))
        groups.append(mates)
    if len(groups) > MAX_FEATURES:
        # Editor's picks first when there are more headliners than slides;
        # the rest still appear on their day slide.
        keep = sorted(groups, key=lambda g: (not any(x.get("pick") for x in g), g[0]["d"], g[0].get("t") or ""))[:MAX_FEATURES]
        groups = sorted(keep, key=lambda g: (g[0]["d"], g[0].get("t") or ""))

    features, names = [], []
    for i, g in enumerate(groups):
        r = g[0]
        title = en(r.get("title")).strip()
        venue = en(r.get("venue")).strip()
        label, art = genre_of(r, en)
        if len(g) > 1:
            head = title.split(":", 1)[0].strip()
            sub = "At %s" % venue
            frows = [[t12(x.get("t")), en(x.get("title")).split(":", 1)[1].strip(),
                      price_line(en(x.get("price")), x.get("free"))] for x in g]
        else:
            head, _, tail = title.partition(" — ")
            head, sub = head.strip(), tail.strip()
            if not sub:
                sub = first_sentence(en(r.get("desc")), head)
            frows = [[t12(r.get("t")), venue, price_line(en(r.get("price")), r.get("free"))]]
        features.append({"art": art, "color": ACCENTS[i % len(ACCENTS)], "day": short_date(r["d"]),
                         "genre": label, "title": head, "sub": sub, "rows": frows})
        names.append((nice(head), d_(r["d"]).weekday()))

    # ---- day slides: everything from today on ---------------------------
    by_day = {}
    for r in lm:
        title = strip_venue(en(r.get("title")).strip(), en(r.get("venue")).strip())
        bits = [en(r.get("venue")).strip()]
        tag = pattern(r)
        price = price_line(en(r.get("price")), r.get("free"))
        if len(title) > 34 and " — " in title:
            # A long "show — performers" title would be shrunk to fit one line
            # until nobody can read it; the performers move down a line instead.
            title, _, who = title.partition(" — ")
            bits.append(who.strip())
        elif tag:
            bits.append(tag)
        elif price:
            bits.append(price[0].lower() + price[1:])
        by_day.setdefault(r["d"], []).append(
            [t12(r.get("t")), title, " · ".join(b for b in bits if b), not r.get("verify")])
    for d in by_day:
        by_day[d].sort(key=lambda x: (not x[3], x[0] == "", dt.datetime.strptime(x[0], "%I:%M %p").time() if x[0] else dt.time(0), x[1].lower()))

    days, dates, i = [], sorted(by_day), 0
    while i < len(dates):
        d = dates[i]
        nxt = dates[i + 1] if i + 1 < len(dates) else None
        if nxt and len(by_day[d]) <= 3 and len(by_day[nxt]) <= 3:
            # Two thin days share a slide; each row then says which day it is.
            merged = [[r[0], r[1], "%s · %s" % (DAY_FULL[d_(x).weekday()], r[2]), r[3]]
                      for x in (d, nxt) for r in by_day[x]]
            days.append({"date": span(d, nxt), "rows": merged,
                         "name": "%s + %s" % (DAY_EN[d_(d).weekday()], DAY_EN[d_(nxt).weekday()])})
            i += 2
            continue
        rws = by_day[d]
        for n, k in enumerate(range(0, len(rws), MAX_DAY_ROWS)):
            days.append({"date": short_date(d), "rows": rws[k:k + MAX_DAY_ROWS],
                         "name": DAY_FULL[d_(d).weekday()] + (" (%d)" % (n + 1) if n else "")})
        i += 1
    for n, day in enumerate(days):
        day["color"] = ACCENTS[n % len(ACCENTS)]

    a, b = d_(week[0]), d_(week[-1])
    slug = ("%s%d-%d" % (MON[a.month - 1], a.day, b.day)).lower()
    n = sum(len(g) for g in groups)
    wk = {
        "slug": slug, "range": span(week[0], week[-1]), "total_listings": total,
        "cover_sub_reel": ("%d headline show%s, then every listing day by day." % (n, "" if n == 1 else "s")
                           if n else "Every live music listing, day by day."),
        "cover_sub_carousel": ("%d confirmed show%s this week." % (n, "" if n == 1 else "s")
                               if n else "Live music all week in Panama City."),
        "features": features, "days": days,
    }

    # ---- caption -------------------------------------------------------
    uniq = []
    for name, wd in names:
        if name.lower() not in [u[0].lower() for u in uniq]:
            uniq.append((name, wd))

    def listing(pairs, days_, joiner):
        parts = ["%s (%s)" % (nm, days_[wd]) for nm, wd in pairs]
        return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " %s " % joiner + parts[-1]

    if uniq:
        es = "Esta semana: %s." % listing(uniq, DAY_ES, "y")
        enl = "This week: %s." % listing(uniq, DAY_EN, "and")
    else:
        es = "Toda la música en vivo de la semana, día por día."
        enl = "Every live music night this week, day by day."
    caption = ("Música en vivo en Panamá esta semana · Live music in Panama City this week\n\n"
               "%s\n%s\n\nAgenda completa / Full week: PanamaLive.AI\n\n%s\n" % (es, enl, HASHTAGS))
    return (wk, caption), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=SITE)
    ap.add_argument("--html", help="read a saved page instead of fetching")
    ap.add_argument("--date", required=True, help="first day to include, YYYY-MM-DD (Panama)")
    ap.add_argument("--out", default="build/week.json")
    ap.add_argument("--caption", default="build/caption.txt")
    a = ap.parse_args()

    rows, tx = load(a)
    res, why = build(rows, tx, a.date)
    if res is None:
        print("nothing to post: %s" % why)
        return 3
    wk, caption = res
    if len(caption) > 2200 or caption.count("#") != 5:
        sys.exit("caption is malformed: %d chars, %d hashtags" % (len(caption), caption.count("#")))
    for p, body in ((a.out, json.dumps(wk, ensure_ascii=False, indent=1)), (a.caption, caption)):
        pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(p).write_text(body, encoding="utf-8")
    print("week %s: %d headline slide(s), %d day slide(s), %d of %d listings from %s on"
          % (wk["range"], len(wk["features"]), len(wk["days"]),
             sum(len(d["rows"]) for d in wk["days"]), wk["total_listings"], a.date))
    for f in wk["features"]:
        print("   headline  %-11s %-26s %s" % (f["day"], f["genre"], f["title"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
