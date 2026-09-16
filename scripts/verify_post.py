#!/usr/bin/env python3
"""
Gate the carousel before it reaches Instagram.

    python3 verify_post.py docs/2026-09-09 --caption build/caption.txt

Every check here exists because it is a way the API rejects a post, or a way a
post goes out looking wrong. Rejections arrive as generic errors long after the
images are committed, so it is much cheaper to fail here.

Mirrors the weekly build's verify.js: do not publish on a FAIL.
"""
import argparse, pathlib, struct, sys

MAXW, MINW = 1440, 320
AR_MIN, AR_MAX = 0.80, 1.91          # Instagram's accepted aspect range
MAX_BYTES = 8 * 1024 * 1024
MAX_SLIDES = 10


def jpeg_size(path):
    """Read dimensions from the SOF marker without a decoder dependency."""
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            return None
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            marker = f.read(1)
            while marker == b"\xff":
                marker = f.read(1)
            if not marker:
                return None
            m = marker[0]
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                continue
            seg = f.read(2)
            if len(seg) < 2:
                return None
            ln = struct.unpack(">H", seg)[0]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                data = f.read(5)
                h, w = struct.unpack(">HH", data[1:5])
                return w, h
            f.seek(ln - 2, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagedir")
    ap.add_argument("--caption", required=True)
    a = ap.parse_args()

    fails, warns = [], []
    imgs = sorted(pathlib.Path(a.imagedir).glob("*.jpg"))

    if not imgs:
        fails.append("no JPEGs in %s" % a.imagedir)
    if len(imgs) > MAX_SLIDES:
        fails.append("%d slides, Instagram allows %d" % (len(imgs), MAX_SLIDES))
    if len(imgs) < 2:
        warns.append("only %d slide(s) -- this posts as a single image, not a "
                     "carousel" % len(imgs))

    sizes = set()
    for p in imgs:
        n = p.stat().st_size
        if n > MAX_BYTES:
            fails.append("%s is %.1f MB, the cap is 8 MB" % (p.name, n / 1e6))
        if n < 8000:
            warns.append("%s is only %d bytes -- did it render?" % (p.name, n))
        wh = jpeg_size(p)
        if not wh:
            fails.append("%s is not a readable JPEG" % p.name)
            continue
        w, h = wh
        sizes.add(wh)
        if not (MINW <= w <= MAXW):
            fails.append("%s is %dpx wide, allowed range is %d-%d"
                         % (p.name, w, MINW, MAXW))
        ar = w / h
        if not (AR_MIN - 1e-9 <= ar <= AR_MAX):
            fails.append("%s aspect ratio %.3f is outside %.2f-%.2f"
                         % (p.name, ar, AR_MIN, AR_MAX))

    # The one that silently ruins a carousel: Instagram crops every slide to
    # the first slide's ratio, so mixed sizes means cropped content.
    if len(sizes) > 1:
        fails.append("slides are not all the same size (%s) -- Instagram crops "
                     "them all to the first one" % ", ".join(
                         "%dx%d" % s for s in sorted(sizes)))

    cap = pathlib.Path(a.caption).read_text(encoding="utf-8")
    ntags = sum(1 for w in cap.split() if w.startswith("#"))
    if len(cap) > 2200:
        fails.append("caption is %d chars, the limit is 2200" % len(cap))
    if ntags > 30:
        fails.append("%d hashtags, the limit is 30" % ntags)
    if not cap.strip():
        fails.append("caption is empty")

    print("verify: %d slide(s), %s, caption %d chars / %d tags"
          % (len(imgs), "%dx%d" % sizes.pop() if len(sizes) == 1 else "mixed",
             len(cap), ntags))
    for w in warns:
        print("  WARN  %s" % w)
    for f in fails:
        print("  FAIL  %s" % f)
    if fails:
        print("\n%d failure(s) -- do not publish." % len(fails))
        return 1
    print("  PASS  ready to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
