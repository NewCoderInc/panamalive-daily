#!/usr/bin/env python3
"""
Ask Buffer whether a queued post actually went out.

    BUFFER_API_KEY=... python3 verify_buffer.py docs/mix/2026-10-08/published.json

publish_buffer.py only proves the post was *queued*: it is scheduled a couple
of minutes ahead and Buffer hands it to Instagram afterwards. "Queued" and
"live" are different claims, and the weekly text message should only say
"posted" for the second. This polls the post until Buffer reports it sent,
and records what it saw in the same state file.

It never fails the run. If Buffer's API will not answer the status query, the
state says "unverified" and the text says so -- an honest "sent, not
confirmed" is worth more than a red X on a post that did go out.
"""
import json, os, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from publish_buffer import API, BufferError, gql, lit  # noqa: E402

SENT = ("sent", "published")
DEAD = ("error", "failed")


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: verify_buffer.py STATE.json [seconds]")
    state = pathlib.Path(sys.argv[1])
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 420
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not state.exists() or not key:
        print("nothing to verify")
        return 0
    rec = json.loads(state.read_text())
    pid = rec.get("buffer_post_id")
    if not pid:
        return 0

    status, deadline = "unverified", time.time() + wait
    while time.time() < deadline:
        try:
            d = gql(API, key, "query { post(input: { id: %s }) { id status } }" % lit(pid))
        except BufferError as e:
            print("buffer would not report the post's status: %s" % e)
            break
        status = ((d.get("post") or {}).get("status") or "unverified").lower()
        print("   buffer status: %s" % status)
        if status in SENT or status in DEAD:
            break
        time.sleep(30)

    rec["status"] = status
    rec["verified"] = status in SENT
    state.write_text(json.dumps(rec), encoding="utf-8")
    print("verified live" if rec["verified"] else "not verified (%s)" % status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
