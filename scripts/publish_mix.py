#!/usr/bin/env python3
"""
Publish the weekly PTY Live Mix reel to Instagram through Buffer's API.

    BUFFER_API_KEY=... python3 publish_mix.py docs/mix/2026-10-08 \
        --caption build/caption.txt \
        --base-url https://newcoderinc.github.io/panamalive-daily/mix/2026-10-08 \
        --state docs/mix/2026-10-08/published.json

Why this is not publish_buffer.py: on its first cloud run (8 Oct 2026) the
weekly reel failed in publish_buffer.py's channel lookup --

    Unknown argument "organizationId" on field "Query.channels".
    Field "channels" argument "input" of type "ChannelsInput!" is required

Buffer's API now wants `channels(input: { organizationId })`. The daily job
fails on the same line every night, and its posts have been going out through
the standby route instead. Fixing the shared file would switch the daily cloud
post back on while that standby is still posting, and the account would get
every day twice. So the weekly reel has its own publisher, and the daily one
is left exactly as it is until its owner decides which route should post.

Two things it does that the shared file does not:

  * the channel is matched on `name` OR `displayName`, still only ever
    @thepanamalive.ai -- any other channel is refused;
  * createPost is tried in a few shapes. Buffer's reference does not show a
    video example, so rather than guess once and lose the week, each shape is
    tried in turn and the first one Buffer accepts wins. A shape Buffer
    rejects creates nothing, so trying the next one cannot double-post.
"""
import argparse, datetime as dt, json, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from publish_buffer import API, TARGET_HANDLE, BufferError, gql, lit, wait_live  # noqa: E402


def find_channel(key, want_id=None):
    orgs = gql(API, key, "query { account { organizations { id } } }")
    orgs = ((orgs.get("account") or {}).get("organizations")) or []
    if not orgs:
        raise BufferError("this API key sees no Buffer organizations")
    seen = []
    for org in orgs:
        d = gql(API, key, "query { channels(input: { organizationId: %s }) "
                          "{ id service name displayName } }" % lit(org["id"]))
        for c in d.get("channels") or []:
            seen.append("%s (%s)" % (c.get("name"), c.get("service")))
            names = {(c.get(k) or "").strip().lstrip("@").lower() for k in ("name", "displayName")}
            if ("instagram" in (c.get("service") or "").lower() and TARGET_HANDLE in names
                    and (not want_id or c.get("id") == want_id)):
                return c["id"], c.get("name")
    raise BufferError("no Instagram channel named @%s in Buffer -- refusing to post "
                      "anywhere else. Connected: %s" % (TARGET_HANDLE, ", ".join(seen) or "none"))


def shapes(url):
    """(label, assets, post metadata) in the order worth trying."""
    with_thumb = "{ video: { url: %s, metadata: { thumbnailOffset: 400 } } }" % lit(url)
    plain = "{ video: { url: %s } }" % lit(url)
    reel = "metadata: { instagram: { type: reel, shouldShareToFeed: true } }"
    return [("video + cover offset", with_thumb, ""),
            ("video + cover offset + reel type", with_thumb, reel),
            ("video + reel type", plain, reel),
            ("video only", plain, "")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--caption", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--wait-for-urls", type=int, default=420)
    ap.add_argument("--delay-minutes", type=int, default=2)
    ap.add_argument("--summary")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    vids = sorted(pathlib.Path(a.dir).glob("*.mp4"))
    if len(vids) != 1:
        sys.exit("expected exactly one MP4 in %s, found %d" % (a.dir, len(vids)))
    url = "%s/%s" % (a.base_url.rstrip("/"), vids[0].name)
    caption = pathlib.Path(a.caption).read_text(encoding="utf-8")
    state = pathlib.Path(a.state)
    if state.exists() and json.loads(state.read_text()).get("buffer_post_id"):
        print("already queued in Buffer for this date -- nothing to do")
        return 0
    print("reel: %s\ncaption: %d chars" % (url, len(caption)), flush=True)
    if a.dry_run:
        print("dry run -- nothing sent to Buffer.")
        return 0

    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key:
        sys.exit("BUFFER_API_KEY must be set in the environment")
    if not wait_live([url], a.wait_for_urls):
        print("FAILED: the reel never went live on Pages, so Buffer could not fetch it", flush=True)
        return 1

    try:
        channel, name = find_channel(key, os.environ.get("BUFFER_CHANNEL_ID", "").strip() or None)
    except BufferError as e:
        print("FAILED: %s" % e, flush=True)
        return 1
    print("channel: %s %s" % (channel, name), flush=True)

    post, why = None, []
    for label, assets, meta in shapes(url):
        due = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=a.delay_minutes)
               ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        q = """mutation {
  createPost(input: {
    text: %s
    channelId: %s
    schedulingType: automatic
    mode: customScheduled
    dueAt: %s
    assets: [%s]
    %s
  }) {
    ... on PostActionSuccess { post { id status dueAt } }
    ... on MutationError { message }
  }
}""" % (lit(caption), lit(channel), lit(due), assets, meta)
        try:
            res = (gql(API, key, q).get("createPost")) or {}
        except BufferError as e:
            why.append("%s: %s" % (label, e))
            print("   Buffer rejected the '%s' shape: %s" % (label, e), flush=True)
            continue
        if (res.get("post") or {}).get("id"):
            post = res["post"]
            print("queued in Buffer as '%s': post %s, status %s, due %s"
                  % (label, post["id"], post.get("status"), post.get("dueAt")), flush=True)
            break
        why.append("%s: %s" % (label, res.get("message") or json.dumps(res)[:200]))
        print("   Buffer refused the '%s' shape: %s" % (label, why[-1]), flush=True)
    if not post:
        print("FAILED: Buffer accepted none of the request shapes.\n   " + "\n   ".join(why), flush=True)
        return 1

    state.write_text(json.dumps({"buffer_post_id": post["id"], "due": post.get("dueAt")}), encoding="utf-8")
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as f:
            f.write("## PTY Live Mix queued to @thepanamalive.ai via Buffer\n\n- Post `%s`, due %s\n"
                    % (post["id"], post.get("dueAt")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
