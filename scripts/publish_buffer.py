#!/usr/bin/env python3
"""
Publish the day's poster to Instagram through Buffer's API.

    BUFFER_API_KEY=... python3 publish_buffer.py docs/2026-09-22 \
        --caption build/caption.txt \
        --base-url https://newcoderinc.github.io/panamalive-daily/2026-09-22

Why Buffer and not Meta directly: publishing through Meta's own API needs a
Meta developer app, and registering one was blocked by Meta's new-device check
on two separate attempts five days apart. Buffer already runs an approved Meta
app; you connect @thepanamalive.ai to Buffer through its normal sign-in and
Buffer publishes on your behalf. No developer account, no access token to
refresh every 60 days. API access is included on Buffer's free plan
(3,000 requests / 30 days; this uses about 3 a day).

Environment:
    BUFFER_API_KEY     required -- Buffer > Settings > API
    BUFFER_CHANNEL_ID  optional -- found automatically as the Instagram channel

Like the direct publisher, Buffer fetches the image from a public URL, so this
waits for GitHub Pages to serve the file before handing it over.
"""
import argparse, datetime as dt, json, os, pathlib, sys, time, urllib.error, urllib.request

API = "https://api.buffer.com"


class BufferError(RuntimeError):
    pass


def gql(api, key, query):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(api, data=body, method="POST", headers={
        "Authorization": "Bearer %s" % key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise BufferError("HTTP %d: %s" % (e.code, e.read().decode(errors="replace")[:400]))
    except urllib.error.URLError as e:
        raise BufferError("network: %s" % e.reason)
    if out.get("errors"):
        raise BufferError("; ".join(x.get("message", str(x)) for x in out["errors"]))
    return out.get("data") or {}


def lit(s):
    """A GraphQL string literal. JSON string escaping is valid GraphQL string
    syntax, so captions with quotes, newlines and emoji survive intact --
    pasting a caption raw into the query is how a stray quote breaks a post."""
    return json.dumps(s, ensure_ascii=False)


# The only account this pipeline may ever post to. A second Instagram channel
# in the same Buffer (e.g. @panamalive.ai) must never receive the daily post,
# so the channel is matched by handle, not just by "is it Instagram".
TARGET_HANDLE = os.environ.get("TARGET_HANDLE", "thepanamalive.ai").strip().lstrip("@").lower()


def find_instagram_channel(api, key, want_id=None):
    orgs = gql(api, key, "query { account { organizations { id name } } }")
    orgs = ((orgs.get("account") or {}).get("organizations")) or []
    if not orgs:
        raise BufferError("this API key sees no Buffer organizations")
    seen = []
    for org in orgs:
        try:
            d = gql(api, key, "query { organization(id: %s) { channels { id service name } } }"
                    % lit(org["id"]))
            chans = ((d.get("organization") or {}).get("channels")) or []
        except BufferError:
            # The docs show both query shapes; accept whichever this account has.
            d = gql(api, key, "query { channels(organizationId: %s) { id service name } }"
                    % lit(org["id"]))
            chans = d.get("channels") or []
        for c in chans:
            seen.append("%s (%s)" % (c.get("name"), c.get("service")))
            name = (c.get("name") or "").strip().lstrip("@").lower()
            if ("instagram" in (c.get("service") or "").lower()
                    and name == TARGET_HANDLE
                    and (not want_id or c.get("id") == want_id)):
                return c["id"], c.get("name")
    raise BufferError("no Instagram channel named @%s%s in Buffer -- refusing to post "
                      "anywhere else. Connected: %s"
                      % (TARGET_HANDLE, " with id %s" % want_id if want_id else "",
                         ", ".join(seen) or "none"))


def wait_live(urls, seconds):
    deadline, pending = time.time() + seconds, list(urls)
    while pending and time.time() < deadline:
        still = []
        for u in pending:
            try:
                with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=15) as r:
                    if r.status != 200:
                        still.append(u)
            except Exception:
                still.append(u)
        pending = still
        if pending:
            print("   %d/%d image(s) live, retrying in 10s" % (len(urls) - len(pending), len(urls)))
            time.sleep(10)
    return not pending


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagedir")
    ap.add_argument("--caption", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--format", choices=("agenda", "carousel", "reel"), default="agenda")
    ap.add_argument("--state", default=None, help="idempotency record")
    ap.add_argument("--wait-for-urls", type=int, default=0, metavar="SECONDS")
    ap.add_argument("--delay-minutes", type=int, default=2,
                    help="schedule this far ahead so Buffer has the post before it is due")
    ap.add_argument("--summary", default=None)
    ap.add_argument("--api", default=API, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    base = a.base_url.rstrip("/")
    if a.format == "reel":
        # A reel is one MP4, and Buffer fetches it from Pages exactly as it
        # fetches a JPEG. Instagram auto-publishes it as a reel because of the
        # 9:16 shape; music baked into the file is part of the video, so it
        # does not trip Buffer's "finish this in the app" path the way
        # Instagram's own audio library would.
        vids = sorted(pathlib.Path(a.imagedir).glob("*.mp4"))
        if not vids:
            sys.exit("no MP4 in %s" % a.imagedir)
        files = vids[:1]
    else:
        files = sorted(pathlib.Path(a.imagedir).glob("*.jpg"))
        if a.format == "agenda":
            files = [p for p in files if p.name.startswith("00_")] or files[:1]
        if not files:
            sys.exit("no JPEGs in %s" % a.imagedir)
        files = files[:10]
    imgs = files
    caption = pathlib.Path(a.caption).read_text(encoding="utf-8")
    urls = ["%s/%s" % (base, p.name) for p in files]

    state = pathlib.Path(a.state) if a.state else None
    if state and state.exists() and json.loads(state.read_text()).get("buffer_post_id"):
        print("already queued in Buffer for this day -- nothing to do")
        return 0

    due = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=a.delay_minutes)
           ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if a.format == "reel":
        # thumbnailOffset picks the cover frame: 400ms in, while the masthead
        # is still on screen, so the grid thumbnail shows the date rather than
        # a half-scrolled list.
        assets = "{ video: { url: %s, metadata: { thumbnailOffset: 400 } } }" % lit(urls[0])
    else:
        assets = ", ".join("{ image: { url: %s } }" % lit(u) for u in urls)
    print("buffer: %d %s, %d-char caption, due %s"
          % (len(urls), "video" if a.format == "reel" else "image(s)",
             len(caption), due))
    for u in urls:
        print("   %s" % u)
    if a.dry_run:
        print("\ndry run -- nothing sent to Buffer.")
        return 0

    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key:
        sys.exit("BUFFER_API_KEY must be set in the environment")

    if a.wait_for_urls and not wait_live(urls, a.wait_for_urls):
        print("FAILED: the media never went live on Pages, so Buffer could not fetch it",
              file=sys.stderr)
        return 1

    try:
        # Even a pinned BUFFER_CHANNEL_ID is checked against the handle, so a
        # mistyped id can never route the post to another account.
        want = os.environ.get("BUFFER_CHANNEL_ID", "").strip() or None
        channel, name = find_instagram_channel(a.api, key, want)
        print("channel: %s %s" % (channel, name))

        d = gql(a.api, key, """mutation {
  createPost(input: {
    text: %s
    channelId: %s
    schedulingType: automatic
    mode: customScheduled
    dueAt: %s
    assets: [%s]
  }) {
    ... on PostActionSuccess { post { id status dueAt } }
    ... on MutationError { message }
  }
}""" % (lit(caption), lit(channel), lit(due), assets))
    except BufferError as e:
        print("\nFAILED: %s" % e, file=sys.stderr)
        return 1

    res = d.get("createPost") or {}
    if res.get("message"):
        print("\nFAILED: Buffer refused the post: %s" % res["message"], file=sys.stderr)
        return 1
    post = res.get("post") or {}
    if not post.get("id"):
        print("\nFAILED: unexpected response from Buffer: %s" % json.dumps(d)[:400],
              file=sys.stderr)
        return 1

    print("\nqueued in Buffer: post %s, status %s, due %s"
          % (post["id"], post.get("status"), post.get("dueAt")))
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as f:
            f.write("## Queued to @thepanamalive.ai via Buffer\n\n"
                    "- Post `%s`, due %s\n- %d %s, %d-char caption\n"
                    % (post["id"], post.get("dueAt"), len(urls),
                       "reel" if a.format == "reel" else "image(s)", len(caption)))
    if state:
        state.write_text(json.dumps({"buffer_post_id": post["id"], "due": due}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
