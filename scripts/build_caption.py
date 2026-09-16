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

MAX_CHARS, MAX_TAGS = 2200, 30

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
    bits = [e.get("venue") or ""]
    t = fmt_time(e.get("time"))
    if t:
        bits.append(t)
    price = (e.get("price") or "").strip()
    if price:
        bits.append(price)
    tail = " · ".join(b for b in bits if b)
    em = CAT_EMOJI.get(e.get("cat") or "", "📅")
    flag = " (outside Panama City)" if e.get("beyond") else ""
    return "%s %s — %s%s" % (em, (e.get("title") or "").strip(), tail, flag)


def build(d, handle_week="PanamaLive.Ai"):
    head = "WHAT'S ON IN PANAMA CITY — %s, %s" % (d["weekday"], d["pretty"])
    lines = [line_for(e) for e in d["shown"]]

    tail = []
    if d.get("overflow"):
        tail.append("+ %d more on today's agenda." % d["overflow"])
    tail.append("Every time and price checked against a primary source.")
    tail.append("Full week → %s" % handle_week)

    tags = list(BASE_TAGS)
    for e in d["shown"]:
        for t in CAT_TAGS.get(e.get("cat") or "", []):
            if t not in tags:
                tags.append(t)
    tags = tags[:MAX_TAGS]

    def assemble(ls):
        return "\n\n".join([head, "\n".join(ls), "\n".join(tail),
                            " ".join(tags)])

    cap = assemble(lines)
    # Drop from the bottom of the listing until it fits -- never mid-sentence,
    # and never from the tags, which are the part that earns reach.
    while len(cap) > MAX_CHARS and len(lines) > 1:
        lines.pop()
        d["overflow"] = d.get("overflow", 0) + 1
        tail[0] = "+ %d more on today's agenda." % d["overflow"]
        cap = assemble(lines)
    return cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", default="caption.txt")
    ap.add_argument("--site", default="PanamaLive.Ai")
    ap.add_argument("--tx", default=None)
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to caption for %s" % d.get("date"))
        return 3

    tx = Tx(a.tx, a.lang)
    d["shown"] = [tx.row(e) for e in d["shown"]]
    print("  translation: %s" % tx.report())

    cap = build(d, a.site)
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
