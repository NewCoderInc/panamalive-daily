#!/usr/bin/env python3
"""
Publish the day's carousel to Instagram via the Content Publishing API.

    python3 publish_instagram.py out/2026-09-09 \
        --caption out/caption.txt \
        --base-url https://user.github.io/panamalive-daily/2026-09-09 \
        --state out/published.json

Environment (never on the command line, never in the repo):
    IG_USER_ID       the Instagram professional account's numeric id
    IG_ACCESS_TOKEN  a long-lived token with instagram_business_content_publish

Three things about this API that bite every first implementation:

1. Instagram fetches the image itself -- "we will cURL your image using the
   passed in URL so it must be on a public server". A local path, a signed URL
   or anything behind auth fails, and it fails at the container step with a
   message that does not say why.

2. Container creation is asynchronous. The POST returns an id immediately, but
   publishing before status_code reaches FINISHED fails intermittently -- which
   is the worst kind of bug, because it passes in testing. So every container
   is polled.

3. Every slide is cropped to the aspect ratio of the FIRST one, and only JPEG
   is accepted. render_cards.py emits uniform 1080x1350 baseline JPEGs, which
   is what makes that safe.

A state file makes the whole thing idempotent: if a run half-completed, or the
schedule fires twice, the day is not posted twice.
"""
import argparse, json, os, pathlib, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://graph.instagram.com"
VERSION = "v23.0"
MAX_SLIDES = 10
POLL_TIMEOUT, POLL_EVERY = 180, 5
# Instagram transcodes a video after fetching it, so a reel container sits in
# IN_PROGRESS for minutes where an image fetch takes seconds. Applying the
# image budget to video fails posts that were going to succeed.
VIDEO_POLL_TIMEOUT = 900


class IGError(RuntimeError):
    pass


def _call(method, path, params, timeout=60):
    url = "%s/%s/%s" % (API, VERSION, path.lstrip("/"))
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        url, data = "%s?%s" % (url, data.decode()), None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            msg = json.loads(body)["error"]
            detail = "%s (code %s%s)" % (
                msg.get("message"), msg.get("code"),
                ", subcode %s" % msg["error_subcode"] if msg.get("error_subcode") else "")
        except Exception:
            detail = body[:400]
        raise IGError("%s %s -> HTTP %d: %s" % (method, path, e.code, detail))
    except urllib.error.URLError as e:
        raise IGError("%s %s -> network: %s" % (method, path, e.reason))


def wait_finished(container_id, token, label, timeout=POLL_TIMEOUT):
    """Poll a container to FINISHED. IN_PROGRESS means Instagram is still
    fetching the image; EXPIRED means we waited too long to publish it."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = _call("GET", container_id,
                  {"fields": "status_code,status", "access_token": token})
        code = r.get("status_code")
        if code != last:
            print("      %s: %s" % (label, code))
            last = code
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise IGError("%s ended as %s -- %s"
                          % (label, code, r.get("status", "no detail")))
        time.sleep(POLL_EVERY)
    raise IGError("%s still %s after %ds" % (label, last, timeout))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagedir")
    ap.add_argument("--caption", required=True)
    ap.add_argument("--base-url", required=True,
                    help="public HTTPS prefix the JPEGs are reachable at")
    ap.add_argument("--state", default=None, help="idempotency record")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate everything, contact nothing")
    ap.add_argument("--wait-for-urls", type=int, default=0, metavar="SECONDS",
                    help="block until every image URL serves 200 before "
                         "publishing (GitHub Pages takes a minute to go live)")
    ap.add_argument("--format", choices=("agenda", "carousel", "reel"), default="agenda",
                    help="agenda posts the single day-poster (00_*.jpg); "
                         "carousel posts the poster plus one slide per event")
    ap.add_argument("--summary", default=None,
                    help="append a run summary to this file (GITHUB_STEP_SUMMARY)")
    a = ap.parse_args()

    if a.format == "reel":
        # One MP4 per day. Sorted rather than taking whatever the filesystem
        # hands back first, so a directory holding two resolves the same way
        # on every run.
        vids = sorted(pathlib.Path(a.imagedir).glob("*.mp4"))
        if not vids:
            sys.exit("no MP4 in %s -- did build_reel.py run?" % a.imagedir)
        imgs = vids[:1]
    else:
        imgs = sorted(pathlib.Path(a.imagedir).glob("*.jpg"))
        if a.format == "agenda":
            imgs = [p for p in imgs if p.name.startswith("00_")] or imgs[:1]
        if not imgs:
            sys.exit("no JPEGs in %s" % a.imagedir)
        if len(imgs) > MAX_SLIDES:
            sys.exit("%d slides -- Instagram allows %d" % (len(imgs), MAX_SLIDES))
    caption = pathlib.Path(a.caption).read_text(encoding="utf-8")
    if len(caption) > 2200:
        sys.exit("caption is %d chars, the limit is 2200" % len(caption))

    base = a.base_url.rstrip("/")
    urls = ["%s/%s" % (base, p.name) for p in imgs]

    state = pathlib.Path(a.state) if a.state else None
    if state and state.exists():
        prev = json.loads(state.read_text())
        if prev.get("published_id"):
            print("already published as %s on %s -- nothing to do"
                  % (prev["published_id"], prev.get("at")))
            return 0

    print("%s: %d image(s), %d-char caption"
          % ("single image" if len(urls) == 1 else "carousel",
             len(urls), len(caption)))
    for u in urls:
        print("   %s" % u)
    if a.dry_run:
        print("\ndry run -- no request made. Confirm each URL above opens in a "
              "private window; Instagram fetches them anonymously.")
        return 0

    if a.wait_for_urls:
        # Pages publishes asynchronously. Instagram fetching a 404 fails the
        # container with a message that blames the image, not the timing, so
        # this check turns a confusing failure into a wait.
        print("\nwaiting for the images to go live")
        deadline = time.time() + a.wait_for_urls
        pending = list(urls)
        while pending and time.time() < deadline:
            still = []
            for u in pending:
                try:
                    req = urllib.request.Request(u, method="HEAD")
                    with urllib.request.urlopen(req, timeout=15) as r:
                        if r.status != 200:
                            still.append(u)
                except Exception:
                    still.append(u)
            if still:
                print("   %d/%d live, retrying in 10s" % (len(urls) - len(still), len(urls)))
                time.sleep(10)
            pending = still
        if pending:
            print("\nFAILED: %d image URL(s) never became reachable, e.g. %s"
                  % (len(pending), pending[0]), file=sys.stderr)
            return 1
        print("   all %d live" % len(urls))

    ig_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not ig_id or not token:
        sys.exit("IG_USER_ID and IG_ACCESS_TOKEN must be set in the environment")

    try:
        if a.format == "reel":
            # media_type=REELS with a public video_url. instagram.com's refusal
            # of 9:16 is a web-uploader quirk, not an API one -- this path is
            # the native reel upload and publishes whatever shape it is given.
            print("\n1. reel container")
            r = _call("POST", "%s/media" % ig_id,
                      {"media_type": "REELS", "video_url": urls[0],
                       "caption": caption, "access_token": token})
            carousel = r["id"]
            print("   %s" % carousel)
            wait_finished(carousel, token, "reel", VIDEO_POLL_TIMEOUT)
        elif len(urls) == 1:
            # A lone image carries its own caption and needs no carousel
            # container. Sending is_carousel_item for a single image builds a
            # container that media_publish then refuses, which is the one way
            # a single-image post fails that a carousel never does.
            print("\n1. image container")
            r = _call("POST", "%s/media" % ig_id,
                      {"image_url": urls[0], "caption": caption,
                       "access_token": token})
            carousel = r["id"]
            print("   %s" % carousel)
            wait_finished(carousel, token, "image")
        else:
            print("\n1. item containers")
            children = []
            for i, u in enumerate(urls, 1):
                r = _call("POST", "%s/media" % ig_id,
                          {"image_url": u, "is_carousel_item": "true",
                           "access_token": token})
                cid = r["id"]
                children.append(cid)
                print("   slide %02d -> %s" % (i, cid))
                wait_finished(cid, token, "slide %02d" % i)

            print("\n2. carousel container")
            r = _call("POST", "%s/media" % ig_id,
                      {"media_type": "CAROUSEL", "children": ",".join(children),
                       "caption": caption, "access_token": token})
            carousel = r["id"]
            print("   %s" % carousel)
            wait_finished(carousel, token, "carousel")

        print("\n3. publish")
        r = _call("POST", "%s/media_publish" % ig_id,
                  {"creation_id": carousel, "access_token": token})
        media_id = r["id"]
    except IGError as e:
        print("\nFAILED: %s" % e, file=sys.stderr)
        print("Nothing was published. Containers expire on their own in 24h.",
              file=sys.stderr)
        return 1

    permalink = ""
    try:
        permalink = _call("GET", media_id,
                          {"fields": "permalink", "access_token": token}
                          ).get("permalink", "")
    except IGError:
        pass

    print("\npublished: %s" % media_id)
    if permalink:
        print("   %s" % permalink)

    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as f:
            f.write("## Posted to @thepanamalive.ai\n\n"
                    "- **%d slides**, %d-char caption\n- Media id `%s`\n%s\n"
                    % (len(urls), len(caption), media_id,
                       "- [View the post](%s)" % permalink if permalink else ""))

    if state:
        state.write_text(json.dumps({
            "published_id": media_id, "permalink": permalink,
            "slides": len(urls), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                     time.gmtime()),
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
