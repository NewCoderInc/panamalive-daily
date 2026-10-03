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
import argparse, base64, html, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tx import Tx  # noqa: E402

# Instagram feed portrait: 1080x1350 (4:5) is the tallest ratio the feed
# allows, so the post owns the most screen while someone scrolls. 1080 wide is
# the sweet spot -- Instagram re-encodes everything, so larger buys nothing.
W, H = 1080, 1350

# The profile grid previews a post at 3:4, NOT at the 4:5 it was posted in, so
# a 4:5 image loses (1080 - 1350*0.75) / 2 = 34px off each side in the
# thumbnail. Side padding must clear that, or right-aligned prices get shaved
# on the grid while looking perfect in the feed. 64px leaves 30px of margin.
GRID_CROP = round((W - H * 0.75) / 2)      # 34
SIDE_PAD = 64
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


AMOUNT_RE = re.compile(r"(US\$|B/\.|\$)\s?(\d+(?:[.,]\d{1,2})?)")


def compact(p, limit=22):
    """A long ladder becomes its entry point -- the lowest real amount.

    Taking the first word instead produced "from Free" for the Miraflores
    visitor centre, which is free only for under-18 nationals; every adult
    pays $3.00. By the house rule that is a paid event, and a poster that
    calls it free sends a family to the gate with the wrong expectation."""
    p = (p or "").strip()
    if len(p) <= limit:
        return p
    # Amounts in parentheses are qualifiers -- an early-bird rate, a fee note --
    # not the price. "US$150 (US$130 early payment until 11 September)" is a
    # US$150 ticket; reading the bracket gave "from US$130" ten days after that
    # rate expired. Only fall back to bracketed amounts if nothing else exists.
    headline = re.sub(r"\([^)]*\)", " ", p)
    found = AMOUNT_RE.findall(headline) or AMOUNT_RE.findall(p)
    amounts = [(float(n.replace(",", ".")), cur, n) for cur, n in found]
    if amounts:
        _, cur, n = min(amounts)
        return "from %s%s" % (cur, n)
    head = re.split(r"\s*[·;]\s*", p)[0].strip()
    return head if len(head) <= limit else head[:limit - 1].rstrip() + "…"


def short_title(t, limit=44):
    """Cut a long title at its dash: "Course: Cities Between Grey and Green —
    Redesigning the relationship..." keeps the part a reader recognises."""
    t = (t or "").strip()
    # "— visit" is the site's marker for standing opening hours. It is useful
    # data (it is how evergreen rows are detected) but noise on the poster,
    # and in a caption it produces "Miraflores — visit — 8:00 AM".
    t = re.sub(r"\s*[—-]\s*(visita|visit)\s*$", "", t, flags=re.I)
    if len(t) > limit and " — " in t:
        return t.split(" — ")[0].strip()
    return t


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
                 esc(short_title(e.get("title"))), esc(e.get("venue")), tag)


def build(d):
    # A festival four hours away does not belong second on a Panama City
    # agenda. The site keeps these on their own Beyond Panama City panel; the
    # poster does the same, and puts that section last.
    BEYOND = "Beyond Panama City"
    buckets = {}
    for e in d["shown"]:
        key = BEYOND if e.get("beyond") else (e.get("cat") or "Other")
        buckets.setdefault(key, []).append(e)
    order = [c for c in CAT_ORDER if c in buckets] + \
            sorted(c for c in buckets if c not in CAT_ORDER and c != BEYOND) + \
            ([BEYOND] if BEYOND in buckets else [])

    body = ""
    for cat in order:
        body += '<div class="hd"><span class="cc">%s</span><span class="ln"></span></div>' \
                % esc(cat.upper())
        body += "".join(row(e) for e in buckets[cat])

    # Always emit the line, hidden when empty: the fit step may trim rows even
    # on a day that started with no overflow, and a trimmed event must still be
    # counted rather than silently disappear.
    n = d.get("overflow") or 0
    more = ('<div class="more" data-n="%d"%s>+%d more today at PanamaLive.Ai</div>'
            % (n, "" if n else ' style="display:none"', n))

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
 padding:26px %(pad)dpx 140px}   /* 126px footer + breathing room */
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
.l2{font-size:96px;margin-top:4px;white-space:nowrap;display:inline-block;
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
.md{min-width:0}
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
 padding:0 %(pad)dpx;z-index:4}
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
   <div class="l2" data-fit-line>%(wd)s %(pretty)s</div></div>
  <div class="bandwrap"><div class="band"><span>%(n)d events across Panama City</span></div></div>
  <div class="list">%(body)s</div>
  %(more)s
 </div>
 <div class="foot">
  <div class="fl"><div class="url">PANAMALIVE.AI</div>
   <div class="tag">DISCOVER &middot; PLAN &middot; ENJOY</div></div>
  <div class="fr"><div class="handle">@thepanamalive.ai</div>
   <div class="scan">DAILY &middot; 7 DAYS A WEEK</div></div>
 </div>
</div>""" % {"W": W, "H": H, "pad": SIDE_PAD,
              "INK": INK, "PINK": PINK, "G1": GOLD1,
              "G2": GOLD2, "TEAL": TEAL, "sky": b64("assets/skyline.jpg"),
              "body": body, "more": more,
              "wd": esc(d["weekday"].upper()), "pretty": esc(d["pretty"].upper()),
              "n": d["total"]}


FIT_JS = """
(function () {
  var l2 = document.querySelector('[data-fit-line]');
  if (l2) {
    var room = l2.parentElement.clientWidth, size = 96;
    while (l2.scrollWidth > room && size > 64) { size -= 2; l2.style.fontSize = size + 'px'; }
  }
})();
(function () {
  var list = document.querySelector('.list'), more = document.querySelector('.more');
  var dropped = 0, guard = 0;
  while (list.scrollHeight > list.clientHeight && list.lastElementChild && guard++ < 60) {
    var el = list.lastElementChild;
    if (el.classList.contains('r')) dropped++;
    list.removeChild(el);
  }
  // A category heading with no rows under it is worse than no heading.
  while (list.lastElementChild && list.lastElementChild.classList.contains('hd')) {
    list.removeChild(list.lastElementChild);
  }
  if (dropped && more) {
    var total = parseInt(more.getAttribute('data-n') || '0', 10) + dropped;
    more.textContent = '+' + total + ' more today at PanamaLive.Ai';
    more.style.display = '';
    // showing the line costs height; re-trim if it pushed the list over
    var g2 = 0;
    while (list.scrollHeight > list.clientHeight && list.lastElementChild && g2++ < 20) {
      var el2 = list.lastElementChild;
      if (el2.classList.contains('r')) { total++; }
      list.removeChild(el2);
      more.textContent = '+' + total + ' more today at PanamaLive.Ai';
    }
    while (list.lastElementChild && list.lastElementChild.classList.contains('hd')) list.removeChild(list.lastElementChild);
  }
  window.__dropped = dropped;
})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--tx", default=None,
                    help="tx.json -- the site's own TX map; the poster is English")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to build")
        return 3
    # The site stores events in the language they were published in and keeps
    # English in TX. Without this the poster prints "Música latina en vivo en
    # The Wine Bar" on an English account -- correct data, wrong language.
    tx = Tx(a.tx, a.lang)
    d["shown"] = [tx.row(e) for e in d["shown"]]
    print("   translation: %s" % tx.report())

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".html")
    tmp.write_text(build(d), encoding="utf-8")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(tmp.resolve().as_uri()); pg.wait_for_timeout(350)
        dropped = pg.evaluate(FIT_JS + "; window.__dropped")
        if dropped:
            print("   trimmed %d row(s) to fit; '+N more' adjusted" % dropped)
        pg.query_selector(".poster").screenshot(path=str(out), type="jpeg",
                                                quality=a.quality)
        b.close()
    tmp.unlink(missing_ok=True)
    print("wrote %s  (%.0f KB)" % (out, out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
