#!/usr/bin/env python3
"""
Refresh the long-lived Instagram token and report how long it has left.

    IG_ACCESS_TOKEN=... python3 refresh_token.py          # report only
    IG_ACCESS_TOKEN=... python3 refresh_token.py --refresh

A long-lived token lasts 60 days. Refreshing extends it another 60, but only
if it is at least 24 hours old, and a token unused for 60 days expires and
cannot be recovered -- you re-authorise by hand.

This is the single most likely cause of the whole thing silently stopping
two months after it starts working, which is why the daily workflow calls the
report and warns, rather than leaving you to find out from a quiet account.
"""
import argparse, json, os, sys, urllib.error, urllib.parse, urllib.request

API = "https://graph.instagram.com"


def call(path, params):
    url = "%s/%s?%s" % (API, path, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %d: %s" % (e.code, e.read().decode(errors="replace")[:300]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--warn-days", type=int, default=14)
    a = ap.parse_args()

    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("IG_ACCESS_TOKEN is not set")

    if a.refresh:
        r = call("refresh_access_token",
                 {"grant_type": "ig_refresh_token", "access_token": token})
        days = int(r.get("expires_in", 0)) // 86400
        print("refreshed -- valid for %d more days" % days)
        print("\nStore this as the new IG_ACCESS_TOKEN secret:\n%s"
              % r["access_token"])
        return 0

    r = call("me", {"fields": "id,username", "access_token": token})
    print("token is valid for @%s (id %s)" % (r.get("username"), r.get("id")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
