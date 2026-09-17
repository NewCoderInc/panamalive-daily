#!/usr/bin/env python3
"""
Build the phone page for posting the day's carousel by hand.

    python3 build_post_page.py today.json --images docs/2026-09-16 \
        --caption build/caption.txt --out docs/2026-09-16/index.html

While the account has no API token, the pipeline still does all the work --
sourcing, ordering, rendering, captioning, checking. Only the final tap is
manual. This page is what makes that tap fast: ten images sized to long-press
and save in order, and the caption behind one Copy button.

Design constraints come from the phone, not the desktop:
  * plain <img> tags, because long-press -> Save to Photos only works on a real
    image element; a CSS background or a canvas cannot be saved;
  * the slide number is OUTSIDE the image, so it is never saved into the photo
    and never posted;
  * the caption is selectable text as well as a Copy button, because clipboard
    permissions fail silently on some mobile browsers.
"""
import argparse, html, json, pathlib, sys

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0d11;color:#f0f2f7;font-family:-apple-system,
  BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.55;padding:0 0 64px}
.wrap{max-width:560px;margin:0 auto;padding:0 18px}
header{padding:26px 0 20px;border-bottom:1px solid #262a35;margin-bottom:24px}
.wm{font-size:15px;font-weight:800;letter-spacing:.26em;text-transform:uppercase}
.wm em{font-style:normal;color:#e4007c}
h1{font-size:27px;font-weight:800;letter-spacing:-.02em;margin:14px 0 6px;
   line-height:1.14}
.sub{font-size:15px;color:#99a1b1}
.how{background:#14161d;border:1px solid #262a35;border-radius:12px;
  padding:16px 18px;margin-bottom:26px;font-size:14.5px;color:#c3c9d6}
.how b{color:#fff}
.how ol{margin:8px 0 0 18px}
.how li{margin:5px 0}
h2{font-size:12px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
   color:#e4007c;margin:32px 0 12px}
.slide{margin-bottom:22px}
.slide .n{font-size:12px;font-weight:700;letter-spacing:.14em;color:#69707f;
  margin-bottom:7px;font-variant-numeric:tabular-nums}
.slide img{display:block;width:100%;border-radius:12px;border:1px solid #333949}
.cap{background:#14161d;border:1px solid #262a35;border-radius:12px;
  padding:16px 18px}
.cap pre{white-space:pre-wrap;word-wrap:break-word;font-family:inherit;
  font-size:14.5px;color:#e4e7ee;-webkit-user-select:text;user-select:text}
button{width:100%;margin-top:14px;padding:14px;border:0;border-radius:10px;
  background:#e4007c;color:#fff;font-size:15px;font-weight:700;cursor:pointer;
  font-family:inherit}
button:active{background:#b80064}
button.done{background:#35d07f;color:#0b0d11}
footer{margin-top:34px;padding-top:18px;border-top:1px solid #262a35;
  font-size:12.5px;color:#69707f}
"""

JS = """
var b=document.getElementById('copy');
b.addEventListener('click',function(){
  var t=document.getElementById('captext').textContent;
  function ok(){b.textContent='Copied';b.className='done';
    setTimeout(function(){b.textContent='Copy caption';b.className='';},2200);}
  if(navigator.clipboard&&window.isSecureContext){
    navigator.clipboard.writeText(t).then(ok,fallback);
  }else{fallback();}
  function fallback(){
    var a=document.createElement('textarea');a.value=t;
    a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);
    a.select();try{document.execCommand('copy');ok();}
    catch(e){b.textContent='Select the text above and copy';}
    document.body.removeChild(a);}
});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("today")
    ap.add_argument("--images", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=("agenda", "carousel"), default="agenda",
                    help="which images the page offers for saving")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.today).read_text(encoding="utf-8"))
    if not d.get("shown"):
        print("nothing to build a page for")
        return 3
    cap = pathlib.Path(a.caption).read_text(encoding="utf-8")
    imgs = sorted(pathlib.Path(a.images).glob("*.jpg"))
    if a.format == "agenda":
        imgs = [p for p in imgs if p.name.startswith("00_")] or imgs[:1]
    if not imgs:
        sys.exit("no images in %s" % a.images)

    slides = "".join(
        '<div class="slide"><div class="n">SLIDE %02d OF %02d</div>'
        '<img src="%s" alt="Slide %d"></div>'
        % (i, len(imgs), html.escape(p.name), i)
        for i, p in enumerate(imgs, 1))

    n = d["total"]
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        '<title>Post for %(pretty)s</title><style>%(css)s</style></head><body>'
        '<div class="wrap"><header>'
        '<div class="wm">PTY <em>LIVE</em></div>'
        '<h1>%(weekday)s, %(pretty)s</h1>'
        '<div class="sub">%(n)d event%(s)s &middot; %(k)d slides ready</div>'
        '</header>'
        '<div class="how"><b>To post:</b>'
        '<ol><li>Long-press each image below and save it &mdash; <b>in order</b>,'
        ' top to bottom.</li>'
        '<li>Tap <b>Copy caption</b> at the bottom.</li>'
        '<li>In Instagram, new post &rarr; select all %(k)d &rarr; check the order'
        ' &rarr; paste the caption.</li></ol></div>'
        '<h2>The slides</h2>%(slides)s'
        '<h2>The caption</h2>'
        '<div class="cap"><pre id="captext">%(cap)s</pre>'
        '<button id="copy">Copy caption</button></div>'
        '<footer>Built automatically from the PanamaLive week. '
        'Times and prices were checked against a primary source; '
        'anything unpublished says so on the card.</footer>'
        '</div><script>%(js)s</script></body></html>'
    ) % {"css": CSS, "js": JS, "slides": slides, "cap": html.escape(cap),
         "weekday": html.escape(d["weekday"]), "pretty": html.escape(d["pretty"]),
         "n": n, "s": "" if n == 1 else "s", "k": len(imgs)}

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%d slides, %d-char caption)" % (out, len(imgs), len(cap)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
