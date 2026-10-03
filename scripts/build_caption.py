#!/usr/bin/env python3
"""
Write the Instagram caption for the day.

    python3 build_caption.py today.json --out caption.txt

English, per the account's editorial setting. The caption repeats the facts
already on the slides on purpose: captions are what Instagram search indexes,
and a reader deciding at 6pm often never swipes past slide one.

Two hard limits, both enforced here rather than discovered at publish time:
a caption is capped at 2,200 characters and 30 hashtags. Going over either
does not truncate gracefully -- the API rejects the whole post.
"""
import argparse, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tx import Tx  # noqa: E402
# One source of truth for how a price and a title are shortened, shared
# with the poster -- otherwise the caption quoted an early-bird rate that
# had expired ten days earlier while the poster, correctly, did not.
from build_brand_poster import compact, short_title  # noqa: E402

MAX_CHARS, MAX_TAGS = 2200, 30
# Instagram allows 30 hashtags on a feed post but only 5 on a REEL, and Buffer
# refuses to queue a reel that breaks it -- found the hard way on the first
# reel we published. --max-tags trims the list for the reel caption.
REEL_TAGS = 5

# Only the house emoji keep-list. One of each per line, same rule as the site.
CAT_EMOJI = {
    "Live Music": "🎤", "Festivals and Concerts": "🎶", "Nightlife": "🎧",
    "Sport": "🎟", "Theatre": "🎟", "Comedy": "🎟",
    "Culture": "📅", "Community": "📅", "Networking": "📅",
}

BASE_TAGS = [
    "#PanamaCity", "#Panama", "#PTY", "#QueHacerEnPanama", "#PanamaEvents",
    "#CascoViejo", "#PanamaNightlife", "#WhatsOnPanama", "#VisitPanama",
    "#PanamaLive", "#EventosPanama", "#PanamaCityPanama",
]
CAT_TAGS = {
    "Live Music": ["#LiveMusicPanama", "#MusicaEnVivo"],
    "Festivals and Concerts": ["#ConciertosPanama", "#FestivalPanama"],
    "Sport": ["#DeportePanama", "#LPF"],
    "Theatre": ["#TeatroPanama"],
    "Comedy": ["#ComedyPanama"],
    "Nightlife": ["#PanamaNights", "#RumbaPanama"],
    "Culture": ["#CulturaPanama", "#ArtePanama"],
    "Community": ["#ComunidadPanama"],
    "Networking": ["#NetworkingPanama"],
}


def fmt_time(t):
    t = (t or "").strip()
    if not t:
        return ""
    try:
        hh, mm = (t.split(":") + ["00"])[:2]
        hh, mm = int(hh), int(mm)
    except ValueError:
        return t
    return "%d:%02d %s" % (hh % 12 or 12, mm, "AM" if hh < 12 else "PM")


def line_for(e):
    title = short_title(e.get("title"))
    venue = (e.get("venue") or "").strip()
    # "Biomuseo — visit — Biomuseo" says the same thing twice.
    bits = [] if venue and venue.lower() in title.lower() else [venue]
    t = fmt_time(e.get("time"))
    if t:
        bits.append(t)
    price = compact(e.get("price"), limit=34)
    if price:
        bits.append(price)
    tail = " · ".join(b for b in bits if b)
    em = CAT_EMOJI.get(e.get("cat") or "", "📅")
    flag = " (outside Panama City)" if e.get("beyond") else ""
    return "%s %s%s%s" % (em, title, (" — " + tail) if tail else "", flag)


def build(d, handle_week="PanamaLive.Ai", promo="", max_tags=MAX_TAGS):
    """Caption = the headline, an optional promo block, then the hashtags.

    Everything factual -- the event list, the times, the prices -- is on the
    poster, and the account's editorial line is that the caption must not
    repeat it. The sourcing note and the "full week" line came out for the
    same reason. The space between the headline and the tags is reserved for
    marketing copy, which --promo drops in unchanged."""
    head = "WHAT'S ON IN PANAMA CITY — %s, %s" % (d["weekday"], d["pretty"])

    # Tags still follow what is actually on today, so reach matches the day.
    tags = list(BASE_TAGS)
    for e in d["shown"]:
        for t in CAT_TAGS.get(e.get("cat") or "", []):
            if t not in tags:
                tags.append(t)
    tags = tags[:max_tags]

    parts = [head] + ([promo.strip()] if promo.strip() else []) + [" ".join(tags)]
    cap = "\n\n".join(parts)
    if len(cap) > MAX_CHARS:            # only reachable via a long promo, so
        over = len(cap) - MAX_CHARS     # trim the promo, never the tags
        raise SystemExit("caption is %d chars -- shorten the promo text by %d"
                         % (len(cap), over))
    return cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", default="caption.txt")
    ap.add_argument("--site", default="PanamaLive.Ai")
    ap.add_argument("--tx", default=None)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--max-tags", type=int, default=MAX_TAGS,
                    help="cap the hashtag block; use %d for a reel caption, "
                         "which Instagram limits to that many" % REEL_TAGS)
    ap.add_argument("--promo", default=None, metavar="FILE",
                    help="marketing copy to place between the headline and "
                         "the hashtags (a text file; blank = no promo block)")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to caption for %s" % d.get("date"))
        return 3

    tx = Tx(a.tx, a.lang)
    d["shown"] = [tx.row(e) for e in d["shown"]]
    print("  translation: %s" % tx.report())

    promo = ""
    if a.promo:
        pf = pathlib.Path(a.promo)
        # A missing promo file must not lose the day's post; the caption is
        # valid without it.
        if pf.exists():
            promo = pf.read_text(encoding="utf-8")
        else:
            print("  no promo file at %s -- caption built without one" % pf)
    cap = build(d, a.site, promo, min(a.max_tags, MAX_TAGS))
    pathlib.Path(a.out).write_text(cap, encoding="utf-8")
    ntags = sum(1 for w in cap.split() if w.startswith("#"))
    print("wrote %s  (%d chars / %d max, %d hashtags / %d max)"
          % (a.out, len(cap), MAX_CHARS, ntags, MAX_TAGS))
    if len(cap) > MAX_CHARS or ntags > MAX_TAGS:
        print("  OVER LIMIT -- Instagram will reject this post")
        return 1
    print("-" * 62); print(cap); print("-" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
