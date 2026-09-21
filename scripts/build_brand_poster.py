#!/usr/bin/env python3
"""
The daily post in the PanamaLive.AI brand style.

    python3 build_brand_poster.py today.json --out docs/2026-09-16/00_agenda.jpg

Built from the brand poster, not from scratch: the Panama City skyline band,
the PanamaLive.AI lockup with LIVE - EXPLORE - EXPERIENCE, the heavy outlined
display headline with a gold second line, the pink brush banner, and the pink
footer bar with the real QR code. Those assets live in assets/ and are cropped
from the brand poster itself, because a regenerated QR would point somewhere
this repo cannot verify.

Where it departs from the brand poster: that one is an advert with four words
on it, this one has to carry a day's listings. So the photo is a band rather
than a full bleed, and the lower half is a solid ground where small type stays
readable. Everything above the fold is brand; everything below it is
information.
"""
import argparse, base64, html, json, pathlib, sys

W, H = 1080, 1350
PINK, GOLD1, GOLD2 = "#ec008c", "#ffe08a", "#f7941e"
TEAL, INK = "#25d0c0", "#140a1e"

CAT_ORDER = ["Live Music", "Festivals and Concerts", "Theatre", "Comedy",
             "Sport", "Culture", "Nightlife", "Community", "Networking"]
HERE = pathlib.Path(__file__).resolve().parent.parent


def esc(s):
    return html.escape((s or "").strip())


def b64(rel):
    p = HERE / rel
    if not p.exists():
        return ""
    mime = "jpeg" if p.suffix in (".jpg", ".jpeg") else "png"
    return "data:image/%s;base64,%s" % (mime, base64.b64encode(p.read_bytes()).decode())


def fmt_time(t):
    t = (t or "").strip()
    if not t:
        return ""
    # A compound showtime ("6 & 8pm") is a real value from a theatre running
    # twice; pass it through rather than mangling it into one time.
    if not t[0].isdigit() or "&" in t or "/" in t:
        return t.lower().replace(" pm", "pm").replace(" am", "am")
    try:
        hh, mm = (t.split(":") + ["00"])[:2]
        hh, mm = int(hh), int(mm)
    except ValueError:
        return t
    return "%d:%02d%s" % (hh % 12 or 12, mm, "am" if hh < 12 else "pm")


def is_free(p):
    return (p or "").strip().lower() in ("free", "gratis", "free entry",
                                         "entrada gratis")


def compact(p, limit=22):
    p = (p or "").strip()
    if len(p) <= limit:
        return p
    head = p.split("·")[0].strip().rstrip(",")
    if len(head) <= limit:
        return head
    first = head.split()[0]
    # "Free for residents; $3 ..." must not become "from Free".
    return "Free" if first.lower().strip(",;") in ("free", "gratis") else "from %s" % first


def row(e):
    t = fmt_time(e.get("time"))
    price = compact(e.get("price"))
    if is_free(price):
        tag = '<span class="free">FREE</span>'
    elif price:
        tag = '<span class="pr">%s</span>' % esc(price)
    else:
        tag = '<span class="tba">TBA</span>'
    return ('<div class="r"><div class="tm">%s</div>'
            '<div class="md"><div class="ti">%s</div>'
            '<div class="vn">%s</div></div><div class="pc">%s</div></div>'
            ) % (esc(t) if t else '<span class="tba">TBA</span>',
                 esc(e.get("title")), esc(e.get("venue")), tag)


def build(d):
    buckets = {}
    for e in d["shown"]:
        buckets.setdefault(e.get("cat") or "Other", []).append(e)
    order = [c for c in CAT_ORDER if c in buckets] + \
            sorted(c for c in buckets if c not in CAT_ORDER)

    body = ""
    for cat in order:
        body += '<div class="hd"><span class="cc">%s</span><span class="ln"></span></div>' \
                % esc(cat.upper())
        body += "".join(row(e) for e in buckets[cat])

    more = ('<div class="more">+%d more today at PanamaLive.Ai</div>'
            % d["overflow"]) if d.get("overflow") else ""

    return """<!doctype html><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000}
.poster{width:%(W)dpx;height:%(H)dpx;position:relative;overflow:hidden;
 color:#fff;font-family:"DejaVu Sans Condensed","DejaVu Sans",
 "Liberation Sans",Arial,sans-serif;background:%(INK)s}
.sky{position:absolute;top:0;left:0;width:100%%;height:430px;
 background-image:url('%(sky)s');background-size:cover;background-position:50%% 42%%}
.sky::after{content:"";position:absolute;inset:0;
 background:linear-gradient(180deg,rgba(20,10,30,.74) 0%%,rgba(20,10,30,.30) 30%%,
  rgba(20,10,30,.62) 66%%,%(INK)s 100%%)}
.body{position:absolute;inset:0;display:flex;flex-direction:column;
 padding:26px 44px 140px}   /* 126px footer + breathing room */
/* ---- lockup ---- */
.lock{position:relative;z-index:3;text-align:center}
.mark{font-size:52px;font-weight:700;letter-spacing:-.022em;line-height:1;
 text-shadow:0 3px 14px rgba(0,0,0,.72)}
.mark b{color:%(PINK)s;font-weight:700}
.sub{font-size:14.5px;font-weight:700;letter-spacing:.34em;margin-top:7px;
 color:rgba(255,255,255,.93);text-shadow:0 2px 8px rgba(0,0,0,.8)}
/* ---- headline ---- */
.head{position:relative;z-index:3;text-align:center;margin-top:26px}
.l1,.l2{position:relative;font-weight:700;line-height:.9;letter-spacing:-.02em;
 text-transform:uppercase}
.l1{font-size:80px;color:#fff;
 text-shadow:0 0 2px %(INK)s,3px 3px 0 %(INK)s,-3px 3px 0 %(INK)s,
  3px -3px 0 %(INK)s,-3px -3px 0 %(INK)s,0 9px 22px rgba(0,0,0,.66)}
.l2{font-size:96px;margin-top:4px;
 background:linear-gradient(180deg,%(G1)s 8%%,%(G2)s 92%%);
 -webkit-background-clip:text;background-clip:text;color:transparent;
 filter:drop-shadow(3px 3px 0 %(INK)s) drop-shadow(-3px -3px 0 %(INK)s)
        drop-shadow(0 10px 20px rgba(0,0,0,.62))}
/* ---- pink brush banner ---- */
.band{position:relative;z-index:3;margin:20px auto 0;display:inline-block;
 background:%(PINK)s;padding:11px 30px 10px;transform:rotate(-1.05deg);
 border-radius:4px 16px 5px 15px;box-shadow:0 6px 20px rgba(0,0,0,.45)}
.band span{font-size:22px;font-weight:700;letter-spacing:.1em;
 text-transform:uppercase;display:block;transform:rotate(.35deg)}
.bandwrap{text-align:center}
/* ---- listings ---- */
.list{position:relative;z-index:3;flex:1;min-height:0;overflow:hidden;
 margin-top:22px}
.hd{display:flex;align-items:center;gap:10px;margin:11px 0 5px}
.cc{background:%(PINK)s;font-size:12.5px;font-weight:700;letter-spacing:.15em;
 padding:4px 11px 3px;border-radius:999px}
.ln{flex:1;height:1px;background:rgba(255,255,255,.2)}
.r{display:grid;grid-template-columns:124px 1fr auto;gap:13px;align-items:center;
 padding:5px 0;border-bottom:1px solid rgba(255,255,255,.085)}
.tm{font-size:15.5px;font-weight:700;color:%(TEAL)s;white-space:nowrap;
 letter-spacing:-.012em;
 font-variant-numeric:tabular-nums}
.ti{font-size:18px;font-weight:700;line-height:1.16;text-transform:uppercase;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vn{font-size:14px;color:rgba(255,255,255,.62);white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.pc{text-align:right}
.pr{font-size:15.5px;font-weight:700;white-space:nowrap}
.free{font-size:12.5px;font-weight:700;letter-spacing:.09em;color:%(INK)s;
 background:%(TEAL)s;padding:3px 9px 2px;border-radius:4px}
.tba{font-size:14px;color:rgba(255,255,255,.42);font-weight:700}
.more{position:relative;z-index:3;flex:none;font-size:15px;font-weight:700;
 color:rgba(255,255,255,.82);margin:10px 0 14px}
/* ---- footer ---- */
.foot{position:absolute;left:0;right:0;bottom:0;height:126px;background:%(PINK)s;
 display:flex;align-items:center;justify-content:space-between;
 padding:0 40px;z-index:4}
.fl .url{font-size:41px;font-weight:700;letter-spacing:-.012em;line-height:1}
.fl .tag{font-size:14.5px;font-weight:700;letter-spacing:.3em;margin-top:6px}
.fr{display:flex;flex-direction:column;align-items:flex-end;gap:5px}
.fr .handle{font-size:27px;font-weight:700;letter-spacing:-.008em;line-height:1}
.fr .scan{font-size:12.5px;font-weight:700;letter-spacing:.2em;
 color:rgba(255,255,255,.88)}
</style>
<div class="poster">
 <div class="sky"></div>
 <div class="body">
  <div class="lock"><div class="mark">Panamá<b>Live.AI</b></div>
   <div class="sub">LIVE &middot; EXPLORE &middot; EXPERIENCE</div></div>
  <div class="head"><div class="l1">Things to do</div>
   <div class="l2">Today</div></div>
  <div class="bandwrap"><div class="band"><span>%(wd)s %(pretty)s &middot; %(n)d events</span></div></div>
  <div class="list">%(body)s</div>
  %(more)s
 </div>
 <div class="foot">
  <div class="fl"><div class="url">PANAMALIVE.AI</div>
   <div class="tag">DISCOVER &middot; PLAN &middot; ENJOY</div></div>
  <div class="fr"><div class="handle">@thepanamalive.ai</div>
   <div class="scan">DAILY &middot; 7 DAYS A WEEK</div></div>
 </div>
</div>""" % {"W": W, "H": H, "INK": INK, "PINK": PINK, "G1": GOLD1,
              "G2": GOLD2, "TEAL": TEAL, "sky": b64("assets/skyline.jpg"),
              "body": body, "more": more,
              "wd": esc(d["weekday"].upper()), "pretty": esc(d["pretty"].upper()),
              "n": d["total"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--tx", default=None, help="tx.json from the weekly build")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to build")
        return 3

    # Same translation pass as the cards and caption, so the poster is not the
    # one Spanish image in an English post.
    from tx import Tx
    tx = Tx(a.tx, a.lang)
    d["shown"] = [tx.row(e) for e in d["shown"]]
    print("  translation: %s" % tx.report())

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".html")
    tmp.write_text(build(d), encoding="utf-8")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(tmp.resolve().as_uri()); pg.wait_for_timeout(350)
        pg.query_selector(".poster").screenshot(path=str(out), type="jpeg",
                                                quality=a.quality)
        b.close()
    tmp.unlink(missing_ok=True)
    print("wrote %s  (%.0f KB)" % (out, out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
