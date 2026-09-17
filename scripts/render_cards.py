#!/usr/bin/env python3
"""
Render the day's carousel as Instagram-ready JPEGs.

    python3 render_cards.py today.json --out out/2026-09-09

Produces 01_cover.jpg .. NN_cta.jpg at 1080x1350 (4:5 -- the tallest ratio the
feed allows, so the card owns the most screen it legally can).

Instagram crops every slide of a carousel to the aspect ratio of the FIRST
slide, so every slide here is rendered at exactly the same size. Getting that
wrong is the classic way to ship a carousel with the venue sliced off slides
2 through 9.

Output is baseline JPEG (not progressive) because Meta's ingestion has
historically rejected some progressive files, and it is the one encoder
setting with no visible downside.
"""
import argparse, hashlib, html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tx import Tx  # noqa: E402

W, H = 1080, 1350

# The site's palette. --accent is the PTY LIVE pink.
ACCENT = "#e4007c"
INK_BG = "#0b0d11"

# shorten_notes.py reduces every Verify note to this fixed vocabulary, joined
# by " · ". A closed set means the English card can look the flag up instead of
# translating it, so a caveat can never be softened or mangled in transit.
NOTE_EN = {
    "Horarios en conflicto": "Conflicting times listed",
    "Hora no publicada": "Start time not published",
    "Precio no publicado": "Price not published",
    "Sede sin confirmar": "Venue unconfirmed",
    "Fecha sin confirmar": "Date unconfirmed",
    "Artista sin anunciar": "Line-up not announced",
    "Patrón semanal, no confirmado para esta fecha":
        "Weekly regular - not confirmed for this date",
    "Sin confirmar con el local": "Not confirmed with the venue",
    "Fuera de la ciudad de Panamá": "Outside Panama City",
    "Sin exposición en cartel": "No exhibition currently showing",
}


def note_en(note):
    """Translate the flag line part-by-part; anything unrecognised passes
    through untouched rather than being dropped, because a note we cannot
    translate is still a warning the reader needs."""
    parts = [p.strip() for p in (note or "").split("·") if p.strip()]
    return " · ".join(NOTE_EN.get(p, p) for p in parts)


CAT_LABEL = {
    "Live Music": "LIVE MUSIC", "Festivals and Concerts": "FESTIVAL",
    "Sport": "SPORT", "Theatre": "THEATRE", "Comedy": "COMEDY",
    "Nightlife": "NIGHTLIFE", "Culture": "CULTURE",
    "Community": "COMMUNITY", "Networking": "NETWORKING",
}


def wash(seed_text):
    """A deterministic stage-light wash, mirroring the site's generated art.

    Same title always yields the same card, so a re-run after a fix does not
    reshuffle the look of the whole day."""
    h = int(hashlib.sha256((seed_text or "x").encode("utf-8")).hexdigest(), 16)
    hue = h % 360
    hue2 = (hue + 40 + (h >> 9) % 60) % 360
    x1, y1 = 12 + (h >> 3) % 70, 8 + (h >> 5) % 34
    x2, y2 = 20 + (h >> 7) % 70, 62 + (h >> 11) % 32
    return (
        "radial-gradient(60% 48% at {x1}% {y1}%, hsla({hue},92%,58%,.60) 0%, "
        "hsla({hue},92%,50%,0) 70%),"
        "radial-gradient(55% 45% at {x2}% {y2}%, hsla({hue2},88%,52%,.46) 0%, "
        "hsla({hue2},88%,45%,0) 72%),"
        "linear-gradient(158deg,#16161f 0%,{bg} 62%)"
    ).format(x1=x1, y1=y1, x2=x2, y2=y2, hue=hue, hue2=hue2, bg=INK_BG)


def esc(s):
    return html.escape((s or "").strip())


def fmt_time(t):
    """24h -> the 8:00 PM shape a reader scans fastest. Never invents one."""
    t = (t or "").strip()
    if not t:
        return ""
    try:
        hh, mm = (t.split(":") + ["00"])[:2]
        hh, mm = int(hh), int(mm)
    except ValueError:
        return t
    ap = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    return "%d:%02d %s" % (h12, mm, ap)


def slide_open(idx, extra_style="", cls=""):
    return '<section class="s{c}" id="s{i}" style="{x}">'.format(
        i=idx, x=extra_style, c=cls)


def cover_html(d):
    n = d["total"]
    line = "%d event%s across Panama City" % (n, "" if n == 1 else "s")
    teaser = "".join(
        '<li>%s</li>' % esc(e.get("title")) for e in d["shown"][:3])
    teaser = ('<ul class="teaser">%s</ul>' % teaser) if teaser else ""
    day = d["weekday"].upper()
    date = d["pretty"].upper()
    return (
        slide_open(0, "background:%s" % wash(d["date"] + "cover")) +
        '<div class="pad">'
        '  <div class="top">'
        '    <div class="wm">PTY <em>LIVE</em></div>'
        '    <div class="site">PanamaLive.Ai</div>'
        '  </div>'
        '  <div class="mid">'
        '    <div class="kicker">WHAT&rsquo;S ON TODAY</div>'
        '    <div class="bigdate">{day}<br><span class="d2">{date}</span></div>'
        '    <div class="rule"></div>'
        '    <div class="count">{line}</div>'
        '    {teaser}'
        '  </div>'
        '  <div class="bot"><span class="swipe">SWIPE FOR TONIGHT&rsquo;S PICKS &rarr;</span></div>'
        '</div></section>'
    ).format(day=esc(day), date=esc(date), line=esc(line), teaser=teaser)


def event_html(e, idx, of):  # noqa: C901
    t = fmt_time(e.get("time"))
    price = (e.get("price") or "").strip()
    note = note_en((e.get("note") or "").strip())
    cat = CAT_LABEL.get(e.get("cat") or "", (e.get("cat") or "EVENT").upper())

    # Both boxes always render. "Not published" in the box is the honest
    # answer and it is where a reader already looks, so the Verify line below
    # does not repeat it -- that line is reserved for things the boxes cannot
    # say (an unconfirmed venue, a weekly regular, conflicting times).
    np = '<span class="np">Not published</span>'
    facts = [
        '<div class="f"><span class="fl">TIME</span><span class="fv">%s</span></div>'
        % (esc(t) if t else np),
        '<div class="f"><span class="fl">ENTRY</span><span class="fv">%s</span></div>'
        % (esc(price) if price else np),
    ]

    venue = esc(e.get("venue") or "")
    addr = esc(e.get("address") or "")
    beyond = ('<span class="tag">OUTSIDE PANAMA CITY</span>'
              if e.get("beyond") else "")
    # Strip flags the card already states plainly elsewhere.
    said = {"Outside Panama City"} if e.get("beyond") else set()
    if not t:
        said.add("Start time not published")
    if not price:
        said.add("Price not published")
    note = " · ".join(p for p in note.split(" · ") if p and p not in said)
    notehtml = ('<div class="note">%s</div>' % esc(note)) if note else ""

    return (
        slide_open(idx, "background:%s" % wash(e.get("title") or str(idx)),
                   cls=" ev") +
        '<div class="pad">'
        '  <div class="top">'
        '    <span class="chip">{cat}</span>'
        '    <span class="num">{i:02d}<span class="of">/{o:02d}</span></span>'
        '  </div>'
        '  <div class="mid">'
        '    {beyond}'
        '    <h1 class="title" data-fit>{title}</h1>'
        '    <div class="venue">{venue}</div>'
        '    {addrhtml}'
        '  </div>'
        '  <div class="bot">'
        '    <div class="facts">{facts}</div>'
        '    {note}'
        '  </div>'
        '</div></section>'
    ).format(cat=esc(cat), i=idx, o=of, beyond=beyond,
             title=esc(e.get("title")), venue=venue,
             addrhtml=('<div class="addr">%s</div>' % addr) if addr else "",
             facts="".join(facts), note=notehtml)


def cta_html(d):
    more = ""
    if d.get("overflow"):
        more = ('<div class="count">+ %d more on today&rsquo;s agenda</div>'
                % d["overflow"])
    return (
        slide_open(99, "background:%s" % wash(d["date"] + "cta")) +
        '<div class="pad">'
        '  <div class="top"><div class="wm">PTY <em>LIVE</em></div></div>'
        '  <div class="mid">'
        '    <div class="kicker">THE WHOLE WEEK</div>'
        '    <div class="bigdate">PANAMA<br><span class="d2">LIVE.AI</span></div>'
        '    <div class="rule"></div>'
        '    {more}'
        '    <div class="gap"></div>'
        '    <div class="count">Times, venues and prices &mdash;<br>checked against the source, every day.</div>'
        '  </div>'
        '  <div class="bot"><span class="swipe">FOLLOW @THEPANAMALIVE.AI</span></div>'
        '</div></section>'
    ).format(more=more)


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000}
body{font-family:Inter,Archivo,"Liberation Sans",Arial,Helvetica,sans-serif;
     -webkit-font-smoothing:antialiased}
.s{width:%(W)dpx;height:%(H)dpx;position:relative;overflow:hidden;color:#fff}
.s::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(6,7,10,.42) 0%%,rgba(6,7,10,0) 26%%,
             rgba(6,7,10,.30) 58%%,rgba(6,7,10,.80) 100%%)}
.pad{position:absolute;inset:0;z-index:2;padding:74px 76px 82px;
     display:flex;flex-direction:column;justify-content:space-between}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px}
.wm{font-size:34px;font-weight:800;letter-spacing:.26em;text-transform:uppercase;
    line-height:1}
.wm em{font-style:normal;color:%(ACCENT)s}
.site{font-size:19px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;
      color:rgba(255,255,255,.72)}
.chip{display:inline-block;background:%(ACCENT)s;color:#fff;font-size:21px;
  font-weight:800;letter-spacing:.17em;padding:11px 20px 10px;border-radius:999px}
.num{font-size:26px;font-weight:800;letter-spacing:.09em;color:rgba(255,255,255,.92)}
.num .of{color:rgba(255,255,255,.48)}
.mid{flex:1;display:flex;flex-direction:column;justify-content:center;
     padding:34px 0}
.s.ev .mid{justify-content:flex-end;padding-bottom:44px}
.kicker{font-size:26px;font-weight:800;letter-spacing:.3em;color:%(ACCENT)s;
        text-transform:uppercase;margin-bottom:26px}
.bigdate{font-size:92px;font-weight:800;line-height:.98;letter-spacing:-.018em;
         text-transform:uppercase}
.bigdate .d2{color:rgba(255,255,255,.62)}
.rule{width:132px;height:7px;background:%(ACCENT)s;margin:38px 0 30px;border-radius:4px}
.count{font-size:32px;font-weight:600;line-height:1.34;color:rgba(255,255,255,.90)}
.gap{height:16px}
.teaser{list-style:none;margin-top:34px;border-top:2px solid rgba(255,255,255,.20);
        padding-top:26px}
.teaser li{font-size:31px;font-weight:700;line-height:1.3;padding:9px 0 9px 32px;
  position:relative;color:rgba(255,255,255,.93);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.teaser li::before{content:"";position:absolute;left:0;top:.62em;width:13px;
  height:13px;border-radius:50%%;background:%(ACCENT)s}
.tag{display:inline-block;border:2px solid rgba(255,255,255,.55);border-radius:6px;
  font-size:19px;font-weight:700;letter-spacing:.14em;padding:7px 13px;
  margin-bottom:24px;color:rgba(255,255,255,.88)}
.title{font-size:82px;font-weight:800;line-height:1.03;letter-spacing:-.021em;
       margin-bottom:30px;overflow-wrap:break-word;hyphens:auto}
.venue{font-size:37px;font-weight:700;line-height:1.24;color:#fff}
.venue::before{content:"";display:inline-block;width:15px;height:15px;
  border-radius:50%%;background:%(ACCENT)s;margin-right:15px;vertical-align:.10em}
.addr{font-size:26px;font-weight:500;line-height:1.34;margin-top:11px;
      color:rgba(255,255,255,.68);padding-left:30px}
.bot{display:flex;flex-direction:column;gap:20px}
.facts{display:flex;gap:20px;flex-wrap:wrap}
.f{background:rgba(255,255,255,.11);border:2px solid rgba(255,255,255,.20);
   border-radius:16px;padding:17px 26px;min-width:230px;
   backdrop-filter:blur(3px)}
.fl{display:block;font-size:18px;font-weight:800;letter-spacing:.19em;
    color:rgba(255,255,255,.62);margin-bottom:7px}
.fv{display:block;font-size:35px;font-weight:800;line-height:1.1}
.np{font-weight:600;color:rgba(255,255,255,.66)}
.note{font-size:23px;font-weight:600;line-height:1.34;color:#ffd9a8;
  border-left:5px solid #f0997b;padding-left:18px}
.swipe{font-size:25px;font-weight:800;letter-spacing:.2em;
       color:rgba(255,255,255,.86)}
""" % {"W": W, "H": H, "ACCENT": ACCENT}

# Long titles are the one thing that can break a fixed-size card. Shrink to fit
# rather than clipping -- a clipped headline is a wrong headline.
FIT_JS = """
document.querySelectorAll('[data-fit]').forEach(function(el){
  var box = el.closest('.mid'), size = parseFloat(getComputedStyle(el).fontSize);
  var guard = 0;
  while (box.scrollHeight > box.clientHeight && size > 34 && guard++ < 90) {
    size -= 2; el.style.fontSize = size + 'px';
  }
});
"""


def build_page(d, cover=True):
    parts = [cover_html(d)] if cover else []
    n = len(d["shown"])
    for i, e in enumerate(d["shown"], start=1):
        parts.append(event_html(e, i, n))
    parts.append(cta_html(d))
    return ("<!doctype html><meta charset='utf-8'><style>%s</style>%s"
            "<script>%s</script>" % (CSS, "".join(parts), FIT_JS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", required=True, help="directory for the JPEGs")
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--keep-html", action="store_true")
    ap.add_argument("--tx", default=None, help="tx.json from the weekly build")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--no-cover", action="store_true",
                    help="skip the cover slide, because the agenda poster "
                         "already leads the carousel")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to render for %s" % d.get("date"))
        return 3

    tx = Tx(a.tx, a.lang)
    d["shown"] = [tx.row(e) for e in d["shown"]]
    print("  translation: %s" % tx.report())

    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    page = outdir / "_slides.html"
    page.write_text(build_page(d, cover=not a.no_cover), encoding="utf-8")

    from playwright.sync_api import sync_playwright

    # Numbering drives the posting order, so it has to stay contiguous whether
    # or not the cover is there -- the poster occupies 00.
    first = 1 if a.no_cover else 2
    names = ([] if a.no_cover else ["01_cover"])
    names += ["%02d_event" % (i + first) for i in range(len(d["shown"]))]
    names.append("%02d_cta" % (len(d["shown"]) + first))

    written = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb",
                                    "--font-render-hinting=none"])
        pg = b.new_page(viewport={"width": W, "height": H},
                        device_scale_factor=1)
        pg.goto(page.resolve().as_uri())
        pg.wait_for_timeout(320)
        for el, name in zip(pg.query_selector_all("section.s"), names):
            f = outdir / ("%s.jpg" % name)
            el.screenshot(path=str(f), type="jpeg", quality=a.quality)
            written.append(f)
        b.close()

    if not a.keep_html:
        page.unlink(missing_ok=True)

    print("rendered %d slide(s) -> %s" % (len(written), outdir))
    for f in written:
        print("   %-16s %6.1f KB" % (f.name, f.stat().st_size / 1024))
    total = sum(f.stat().st_size for f in written) / 1024 / 1024
    print("   total %.2f MB  (Instagram cap is 8 MB per image)" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
