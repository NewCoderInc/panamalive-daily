#!/usr/bin/env python3
"""
Turn a day's agenda into a 9:16 Instagram reel that scrolls the poster.

    python3 build_reel.py today.json --out reel.mp4 --tx tx.json

Why a separate tall render rather than panning the 1080x1350 feed poster:
a 4:5 image is SHORTER than a 9:16 frame, so there is nothing to scroll --
it would letterbox or crop the headline away. So the same builder is asked
for a tall canvas (every event, no '+N more' trimming), and the video pans a
1080x1920 window down it. The first and last seconds hold still, because a
reel that is already moving when it appears reads as a glitch.

Audio: --audio takes a WAV/MP3 to lay under the scroll. make_bed.py writes an
original loop for exactly this, because a commercial track on a business
account is a copyright strike waiting to happen. Instagram can still layer a
licensed track from its own library over the upload.

--cta paints a call to action over the last seconds, fading in as the footer
arrives, so the ask lands when the viewer has already read the agenda.

Still mode: when the whole day is only a little taller than the frame (a
light day -- 9 events overshot a 4:5 frame by 35px), a scroll is a twitch that
reads as a glitch. Within --still-slack px the reel does not scroll at all: the
poster is re-rendered to fill the frame exactly, stepping --zoom down only as
far as needed so every row fits. The CTA and audio are unchanged.

Long titles: the poster clips a title with an ellipsis on one line, which is
right at 1080px but at --zoom 1.3 (831px layout) cuts real words off. The reel
render lets titles wrap to a second line instead; the height is measured
afterwards, so wrapping costs a row's height, never a word.
"""
import argparse, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_brand_poster as bp  # noqa: E402
from tx import Tx  # noqa: E402

FRAME_W, FRAME_H = 1080, 1920
# Instagram's WEB uploader takes feed video only, and a feed video must be
# between 4:5 and 1.91:1 -- a 9:16 file stalls the upload with no error at all.
# 4:5 is the tallest shape it will accept, so --shape feed renders 1080x1350
# and the same file still plays full-bleed in the Reels tab on a phone.
SHAPES = {"reel": 1920, "feed": 1350, "square": 1080}
CTA_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
ROW_PX = 66          # measured height of one event row at this type size
BASE_PX = 900        # masthead + band + footer + breathing room


# The headline is sized to fill 1080px and only the poster's fit pass shrinks
# it, so a tall render without this ships a masthead cut off mid-word. The row
# trimming from that pass is deliberately NOT reused -- a reel has room for the
# whole day.
HEAD_FIT = """
(function () {
  var l2 = document.querySelector('[data-fit-line]');
  if (!l2) { return 0; }
  var room = l2.parentElement.clientWidth * 0.94, size = 96;
  l2.style.fontSize = size + 'px';
  while (l2.scrollWidth > room && size > 40) { size -= 2; l2.style.fontSize = size + 'px'; }
  // Keep the white line in proportion to the gold one (the 80/96 of the
  // brand poster), so a long date shrinks the pair instead of leaving a
  // headline whose second line is smaller than its first.
  var l1 = document.querySelector('.l1');
  if (l1) { l1.style.fontSize = Math.round(size * 80 / 96) + 'px'; }
  return size;
})();
"""

# How much blank canvas sits under the last row. Measured rather than guessed:
# the first pass renders deliberately too tall and reports where the list ends.
MEASURE = """
(function () {
  var list = document.querySelector('.list');
  var last = list.lastElementChild;
  return last ? last.getBoundingClientRect().bottom : 0;
})();
"""


# Injected into every reel render (see "Long titles" above). minmax(0,1fr)
# stops a long title from pushing the price column off the right edge.
REEL_CSS = """
(function () {
  var st = document.createElement('style');
  st.textContent = '.r{grid-template-columns:124px minmax(0,1fr) auto}' +
    '.ti{white-space:normal;overflow:visible;text-overflow:clip;' +
    'overflow-wrap:anywhere}';
  document.head.appendChild(st);
  return 1;
})();
"""


def _open(b, d, html, height):
    bp.H = height
    html.write_text(bp.build(d), encoding="utf-8")
    pg = b.new_page(viewport={"width": bp.W, "height": height},
                    device_scale_factor=1)
    pg.goto(html.resolve().as_uri())
    pg.wait_for_timeout(350)
    pg.evaluate(REEL_CSS)
    pg.evaluate(HEAD_FIT)
    return pg


def render_still(d, out_png, zoom, floor=1.0, step=0.05):
    """Render the day to fill exactly one FRAME_W x FRAME_H frame, no scroll.

    Tries `zoom` first and steps it down toward `floor` until every row plus
    the footer fits in the frame. Returns the zoom used, or None if even
    `floor` does not fit (the caller then falls back to scrolling)."""
    from playwright.sync_api import sync_playwright
    html = pathlib.Path(str(out_png) + ".html")
    used = None
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        z = zoom
        while z >= floor - 1e-9:
            bp.W = int(round(FRAME_W / z))
            css_h = int(round(FRAME_H / z))
            pg = _open(b, d, html, css_h + 2000)     # measure on a tall canvas
            need = pg.evaluate(MEASURE) + 190
            pg.close()
            if need <= css_h:
                pg = _open(b, d, html, css_h)
                pg.query_selector(".poster").screenshot(path=str(out_png))
                pg.close()
                used = z
                break
            z = round(z - step, 3)
        b.close()
    html.unlink(missing_ok=True)
    if used is not None:
        from PIL import Image
        im = Image.open(out_png)
        if im.size != (FRAME_W, FRAME_H):
            im.resize((FRAME_W, FRAME_H), Image.LANCZOS).save(out_png)
    return used


def render_tall(d, out_png, height, zoom=1.0):
    """Screenshot the poster on a tall canvas, keeping every row.

    `zoom` renders narrower than 1080 and scales the image back up, which makes
    the type bigger for a phone AND lengthens the scroll -- a reel whose
    content is barely taller than the frame reads as a still image.

    Two passes: the first measures where the last event row actually ends, the
    second re-renders at that height so the footer sits just under the list
    instead of after a screen of empty purple."""
    html = pathlib.Path(str(out_png) + ".html")
    bp.W = int(round(FRAME_W / zoom))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        for attempt in (1, 2):
            pg = _open(b, d, html, height)
            if attempt == 1:
                bottom = pg.evaluate(MEASURE)
                pg.close()
                # list bottom + the footer band and its margin
                height = int(bottom + 190)
                continue
            pg.query_selector(".poster").screenshot(path=str(out_png))
            pg.close()
        b.close()
    html.unlink(missing_ok=True)
    if zoom != 1.0:
        from PIL import Image
        im = Image.open(out_png)
        height = int(round(im.height * FRAME_W / im.width))
        im.resize((FRAME_W, height), Image.LANCZOS).save(out_png)
    return height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tx", default=None)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--shape", choices=tuple(SHAPES), default="reel",
                    help="reel = 1080x1920 (9:16), feed = 1080x1350 (4:5, the "
                         "only tall shape Instagram's web uploader accepts)")
    ap.add_argument("--zoom", type=float, default=1.3,
                    help="render this much narrower than 1080 and scale up: "
                         "bigger type on a phone and a longer scroll")
    ap.add_argument("--hold", type=float, default=1.5,
                    help="still seconds at the start and at the end")
    ap.add_argument("--audio", default=None,
                    help="WAV/MP3 to lay under the video (trimmed to length)")
    ap.add_argument("--cta", default=None,
                    help="call to action painted over the last seconds")
    ap.add_argument("--cta-seconds", type=float, default=3.2,
                    help="how long the call to action is on screen")
    ap.add_argument("--still-slack", type=int, default=240, metavar="PX",
                    help="if the tall render overshoots the frame by at most "
                         "this much (or falls short), don't scroll: fill one "
                         "still frame instead. 0 = always scroll")
    a = ap.parse_args()

    global FRAME_H
    FRAME_H = SHAPES[a.shape]

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to build")
        return 3
    tx = Tx(a.tx, a.lang)
    d["shown"] = [tx.row(e) for e in d["shown"]]
    print("   translation: %s" % tx.report())

    # One row per event plus one header per category, then round up so the
    # last row never lands flush against the footer.
    cats = len({e.get("cat") for e in d["shown"]})
    tall = max(FRAME_H + 200, BASE_PX + (len(d["shown"]) + cats) * ROW_PX)
    tall = int(tall)

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".png")
    tall = render_tall(d, png, tall, a.zoom)
    print("   tall poster: 1080x%d (%d events)" % (tall, len(d["shown"])))

    still = None
    if a.still_slack > 0 and tall - FRAME_H <= a.still_slack:
        still = render_still(d, png, a.zoom)
    if still is not None:
        print("   still frame: only %+dpx past the frame, no scroll (zoom %.2f)"
              % (tall - FRAME_H, still))
        vf = "scale=%d:%d" % (FRAME_W, FRAME_H)
    else:
        if tall < FRAME_H:
            sys.exit("tall render (%dpx) is shorter than the frame and would "
                     "not fit still either" % tall)
        travel = a.seconds - 2 * a.hold
        # smoothstep, so the scroll eases in and out instead of starting at speed
        p = "clip((t-%.3f)/%.3f,0,1)" % (a.hold, travel)
        y = "(ih-%d)*(%s*%s*(3-2*%s))" % (FRAME_H, p, p, p)
        vf = "crop=%d:%d:0:'%s'" % (FRAME_W, FRAME_H, y)

    if a.cta:
        t0 = a.seconds - a.cta_seconds
        # Fade in over 0.5s rather than cutting, and sit above the pink footer
        # band, which is where the eye already is by the end of the scroll.
        # Two lines, because one line of this at a readable size is wider than
        # 1080 and ffmpeg does not wrap -- it just runs off both edges.
        alpha = "min((t-%.2f)/0.5,1)" % t0
        # A dark band behind it: the text lands over event rows, and white on
        # a busy list is unreadable however big the type is.
        # Positions are proportional so the band sits just above the footer in
        # every shape -- a fixed 660px offset lands mid-frame on a 4:5 video.
        band_y = int(FRAME_H * 0.655)
        vf += (",drawbox=x=0:y=%d:w=iw:h=236:color=0x140a1e@0.86:t=fill"
               ":enable='gte(t,%.2f)'" % (band_y, t0))
        lines = [l.strip() for l in a.cta.split("|")]
        for i, line in enumerate(lines):
            vf += (",drawtext=fontfile=%s:text='%s':fontsize=%d"
                   ":fontcolor=white:shadowcolor=0x140a1e@0.9:shadowx=0:shadowy=3"
                   ":x=(w-text_w)/2:y=%d:enable='gte(t,%.2f)':alpha='%s'"
                   % (CTA_FONT, line.replace("'", ""), 72 if i == 0 else 56,
                      band_y + (36 if i == 0 else 128), t0, alpha))
    vf += ",format=yuv420p"

    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(png)]
    if a.audio:
        cmd += ["-i", a.audio]
    cmd += ["-t", "%.2f" % a.seconds, "-vf", vf,
            "-r", "30", "-c:v", "libx264", "-preset", "slow", "-crf", "20"]
    if a.audio:
        # Instagram re-encodes anyway; AAC 128k stereo is what it expects, and
        # -shortest keeps a longer bed from padding the video.
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-shortest",
                "-af", "afade=t=out:st=%.2f:d=1.0" % max(a.seconds - 1.0, 0)]
    cmd += ["-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-1500:], file=sys.stderr)
        return 1
    png.unlink(missing_ok=True)
    print("wrote %s  (%.1f MB, %.0fs, %dx%d)"
          % (out, out.stat().st_size / 1e6, a.seconds, FRAME_W, FRAME_H))
    return 0


if __name__ == "__main__":
    sys.exit(main())
