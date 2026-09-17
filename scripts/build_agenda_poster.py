#!/usr/bin/env python3
"""
One dense "whole day at a glance" poster, in the PanamaLive.Ai house style.

    python3 build_agenda_poster.py today.json --out docs/2026-09-16/00_agenda.jpg

The carousel explains events one at a time; this shows the shape of the day in
a single frame, which is what earns a stop in the feed. It is the same data,
laid out for scanning rather than swiping.

House style is taken from the website, not from the reference post that
prompted it: the PTY LIVE lockup, the #e4007c pink, uppercase card titles,
category headers with a count, and the price ladder written the way the site
writes it. The density comes from the reference; none of the neon does.
"""
import argparse, html, json, pathlib, sys

W, H = 1080, 1350
ACCENT, TEAL = "#e4007c", "#14b8a6"

CAT_ORDER = ["Live Music", "Festivals and Concerts", "Theatre", "Comedy",
             "Sport", "Culture", "Nightlife", "Community", "Networking"]


def esc(s):
    return html.escape((s or "").strip())


def fmt_time(t):
    t = (t or "").strip()
    if not t:
        return ""
    if not t[0].isdigit():          # already "6:00 & 8:00 PM"
        return t
    try:
        hh, mm = (t.split(":") + ["00"])[:2]
        hh, mm = int(hh), int(mm)
    except ValueError:
        return t
    return "%d:%02d %s" % (hh % 12 or 12, mm, "AM" if hh < 12 else "PM")


def is_free(p):
    return (p or "").strip().lower() in ("free", "gratis", "free entry",
                                         "entrada gratis")


def compact_price(p, limit=26):
    """Long ladders belong on the website; the poster carries the entry point."""
    p = (p or "").strip()
    if len(p) <= limit:
        return p
    head = p.split("·")[0].strip().rstrip(",")
    low = head.split()[0] if head else p
    return head if len(head) <= limit else ("from %s" % low)


def sub(e):
    """Second line: the venue, or the address when the venue just repeats the
    title -- "BIOMUSEO / Biomuseo" tells a reader nothing they cannot see."""
    v, t = (e.get("venue") or "").strip(), (e.get("title") or "").strip()
    if v and v.lower().rstrip(".") not in t.lower():
        return v
    return (e.get("address") or v)


def row(e):
    t = fmt_time(e.get("time"))
    price = compact_price(e.get("price"))
    if is_free(price):
        tag = '<span class="free">FREE</span>'
    elif price:
        tag = '<span class="price">%s</span>' % esc(price)
    else:
        tag = '<span class="tba">Price TBA</span>'
    pick = '<span class="pick">&#9733;</span>' if e.get("pick") else ""
    return (
        '<div class="r">'
        '<div class="t">%s</div>'
        '<div class="m"><div class="ti">%s%s</div><div class="v">%s</div></div>'
        '<div class="pc">%s</div>'
        '</div>'
    ) % (esc(t) if t else '<span class="tba">TBA</span>',
         pick, esc(e.get("title")), esc(sub(e)), tag)


def build(d):
    groups, seen = [], {}
    for e in d["shown"]:
        seen.setdefault(e.get("cat") or "Other", []).append(e)
    for cat in CAT_ORDER:
        if cat in seen:
            groups.append((cat, seen.pop(cat)))
    groups += sorted(seen.items())

    body = ""
    for cat, evs in groups:
        body += ('<div class="h"><span class="chip">%s</span>'
                 '<span class="n">%d</span><span class="rule"></span></div>'
                 % (esc(cat.upper()), len(evs)))
        body += "".join(row(e) for e in evs)

    more = ""
    if d.get("overflow"):
        more = ('<div class="more">+ %d more today &mdash; full listings, '
                'every venue and price, at PanamaLive.Ai</div>' % d["overflow"])

    return """<!doctype html><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000}
.poster{width:%(W)dpx;height:%(H)dpx;position:relative;overflow:hidden;color:#fff;
 font-family:Inter,"Liberation Sans",Arial,sans-serif;
 background:radial-gradient(70%% 42%% at 78%% -6%%,rgba(228,0,124,.34) 0%%,rgba(228,0,124,0) 62%%),
            radial-gradient(64%% 38%% at 12%% -4%%,rgba(99,102,241,.32) 0%%,rgba(99,102,241,0) 66%%),
            linear-gradient(176deg,#15151f 0%%,#0b0d11 46%%)}
.in{position:absolute;inset:0;display:flex;flex-direction:column;
 padding:34px 46px 30px}
.bar{display:flex;align-items:baseline;justify-content:space-between;
 padding-bottom:20px;border-bottom:1px solid rgba(255,255,255,.16)}
.wm{font-size:23px;font-weight:800;letter-spacing:.27em;text-transform:uppercase}
.wm em{font-style:normal;color:%(A)s}
.site{font-size:14px;font-weight:600;letter-spacing:.17em;
 color:rgba(255,255,255,.6);text-transform:uppercase}
.hero{padding:22px 0 16px}
.kick{font-size:17px;font-weight:800;letter-spacing:.3em;color:%(A)s;
 text-transform:uppercase;margin-bottom:12px}
.date{font-size:60px;font-weight:800;line-height:.96;letter-spacing:-.025em;
 text-transform:uppercase}
.date span{color:rgba(255,255,255,.56)}
.cnt{font-size:20px;font-weight:600;color:rgba(255,255,255,.82);margin-top:14px}
.list{flex:1;min-height:0;overflow:hidden;display:flex;
 flex-direction:column;justify-content:flex-start}
.h{display:flex;align-items:center;gap:11px;margin:13px 0 7px}
.chip{background:%(A)s;font-size:13px;font-weight:800;letter-spacing:.16em;
 padding:5px 12px 4px;border-radius:999px}
.n{font-size:13px;font-weight:800;color:rgba(255,255,255,.5);
 font-variant-numeric:tabular-nums}
.rule{flex:1;height:1px;background:rgba(255,255,255,.15)}
.r{display:grid;grid-template-columns:140px 1fr auto;gap:16px;align-items:center;
 padding:6px 0;border-bottom:1px solid rgba(255,255,255,.07)}
.t{font-size:17px;font-weight:800;font-variant-numeric:tabular-nums;
 color:#fff;white-space:nowrap;letter-spacing:-.01em}
.ti{font-size:18px;font-weight:700;line-height:1.2;text-transform:uppercase;
 letter-spacing:-.004em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.v{font-size:14.5px;font-weight:500;color:rgba(255,255,255,.62);margin-top:1px;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pick{color:%(A)s;margin-right:7px}
.pc{text-align:right}
.price{font-size:16px;font-weight:700;color:rgba(255,255,255,.9);white-space:nowrap}
.free{font-size:13px;font-weight:800;letter-spacing:.11em;color:#0b0d11;
 background:%(T)s;padding:4px 10px 3px;border-radius:5px}
.tba{color:rgba(255,255,255,.4);font-weight:600}
.more{font-size:16px;font-weight:600;color:rgba(255,255,255,.78);
 margin-top:12px;line-height:1.4;flex:none}
.foot{display:flex;align-items:center;justify-content:space-between;
 margin-top:18px;padding-top:16px;border-top:1px solid rgba(255,255,255,.16)}
.hand{font-size:19px;font-weight:800;letter-spacing:.12em}
.tag{font-size:14px;font-weight:600;letter-spacing:.14em;
 color:rgba(255,255,255,.58);text-transform:uppercase}
</style>
<div class="poster"><div class="in">
 <div class="bar"><div class="wm">PTY <em>LIVE</em></div>
  <div class="site">PanamaLive.Ai</div></div>
 <div class="hero"><div class="kick">What&rsquo;s on today</div>
  <div class="date">%(wd)s<br><span>%(pretty)s</span></div>
  <div class="cnt">%(n)d events across Panama City</div></div>
 <div class="list">%(body)s</div>
 %(more)s
 <div class="foot"><div class="hand">@THEPANAMALIVE.AI</div>
  <div class="tag">Checked against the source</div></div>
</div></div>""" % {"W": W, "H": H, "A": ACCENT, "T": TEAL, "body": body,
                   "more": more, "wd": esc(d["weekday"].upper()),
                   "pretty": esc(d["pretty"].upper()), "n": d["total"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", type=int, default=90)
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to build")
        return 3

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".html")
    tmp.write_text(build(d), encoding="utf-8")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(tmp.resolve().as_uri()); pg.wait_for_timeout(280)
        pg.query_selector(".poster").screenshot(path=str(out), type="jpeg",
                                           quality=a.quality)
        b.close()
    tmp.unlink(missing_ok=True)
    print("wrote %s  (%.0f KB)" % (out, out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
