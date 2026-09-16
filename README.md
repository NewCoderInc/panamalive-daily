# PanamaLive Daily — automated Instagram carousel for @thepanamalive.ai

Posts one carousel a day at **07:00 Panama time**: a cover slide, up to eight
event slides, and a closing card pointing at PanamaLive.Ai.

The judgement happens once a week. The posting happens every day, and is
deliberately dumb.

```
  WEEKLY  (you + Claude, ~once)          DAILY  (GitHub Actions, unattended)
  ─────────────────────────────          ──────────────────────────────────
  pty-week build                         07:00 Panama
    pull ~15 sources                       select_today.py   slice to one day
    deep-dive times/venues/prices          render_cards.py   10 JPEGs
    translate to EN                        build_caption.py  caption + tags
        ↓                                  verify_post.py    gate
     events.json  ──────────────────────►  commit to docs/   Pages serves them
     tx.json                               publish_instagram.py
                                              ↓
                                           @thepanamalive.ai
```

Everything the daily job publishes was already verified in the weekly pass. It
invents nothing, guesses no times, and translates nothing on the fly — so there
is no unattended step where an editorial mistake can be introduced.

---

## Why GitHub Actions and not a Claude scheduled task

Meta's publishing endpoints (`graph.instagram.com`) are not reachable from the
Claude cloud sandbox — the egress gateway answers `403` to the CONNECT. So a
scheduled Claude session physically cannot post, no matter how it is written.

Actions solves three problems at once, free on a public repo:

- **network** — unrestricted, so the Graph API is reachable;
- **image hosting** — Instagram fetches images itself and *"it must be on a
  public server"*. GitHub Pages serves `docs/` over HTTPS at no cost;
- **a real scheduler** — one that runs whether or not any machine is awake.

## One-time setup

**1. The Instagram account.** `@thepanamalive.ai` must be a **professional**
account (Business or Creator) — Settings → Account type. A personal account
cannot be posted to by any API, by anyone.

**2. A Meta app.** [developers.facebook.com](https://developers.facebook.com) →
create an app → add **Instagram** → *Instagram API with Instagram Login*. That
setup does **not** require a linked Facebook Page. Request the scopes
`instagram_business_basic` and `instagram_business_content_publish`.

**3. A long-lived token.** Authorise through the app, then exchange the
short-lived token at `graph.instagram.com/access_token`. Check it with:

```bash
IG_ACCESS_TOKEN=... python3 scripts/refresh_token.py
```

**4. This repo.**

```bash
gh repo create panamalive-daily --public --source . --push
```

Settings → Pages → deploy from branch `main`, folder `/docs`.

Settings → Secrets and variables → Actions:

| Kind | Name | Value |
|---|---|---|
| Secret | `IG_USER_ID` | numeric id from `refresh_token.py` |
| Secret | `IG_ACCESS_TOKEN` | the long-lived token |
| Variable | `PAGES_BASE_URL` | `https://<you>.github.io/panamalive-daily` |

**5. The week's data.** Drop `events.json` and `tx.json` from the weekly
`pty-week` build in the repo root and push. That is the only recurring task.

**6. Dry-run it.** Actions → *Daily Instagram post* → Run workflow, with
**dry run** ticked. It builds and commits the cards without posting. Open the
Pages URL and look at them.

## The weekly hand-off

```bash
# after the pty-week build
cp pty-week/events.json pty-week/tx.json .
git commit -am "Week of $(date +%F)" && git push
```

Nothing else is needed. The daily job reads whatever `events.json` holds and
posts the rows dated for that day; a day with no rows is skipped cleanly
rather than posting an empty carousel.

## Running it by hand

```bash
./scripts/run_local.sh                  # today, build only, no credentials
./scripts/run_local.sh 2026-09-12       # a future day, to preview the cards
./scripts/run_local.sh 2026-09-12 post  # build and publish
```

## What each script does

| Script | Job |
|---|---|
| `select_today.py` | Slices `events.json` to one day, orders it by the site's own `CAT_PRIORITY`, caps it at 8 event slides |
| `render_cards.py` | 1080×1350 JPEGs via Playwright — cover, event slides, closing card |
| `build_caption.py` | English caption, house emoji only, under 2,200 chars and 30 tags |
| `tx.py` | Shared `tx.json` lookup, and **reports** untranslated strings instead of silently falling through |
| `verify_post.py` | The gate: uniform sizes, aspect ratio, byte caps, caption limits |
| `publish_instagram.py` | Container → poll → carousel → publish, with a state file so a day is never posted twice |
| `refresh_token.py` | Token health, and the 60-day refresh |

## Things that will eventually go wrong

**The token expires.** Long-lived tokens last 60 days. `refresh-token.yml`
runs monthly and prints a fresh one into the run log — paste it into the
`IG_ACCESS_TOKEN` secret. If a token goes 60 days unused it cannot be
refreshed and you re-authorise by hand. The daily job also checks the token
every run and raises a warning, so this shows up before it breaks anything.

**`events.json` goes stale.** The daily job cannot tell a quiet Tuesday from a
week nobody rebuilt — both look like zero rows. It skips the post and writes a
notice in the run log rather than posting a thin carousel.

**Slides come out cropped.** Instagram crops every slide to the aspect ratio of
the *first* one. `verify_post.py` fails the run if the sizes are not identical.

**Pages hasn't deployed yet.** The publisher polls every image URL for up to
five minutes before it calls the API, because Instagram fetching a 404 fails
with an error that blames the image rather than the timing.

## Limits worth knowing

- 100 API-published posts per 24 hours (a carousel counts as one)
- 10 slides per carousel — hence the cap of 8 events plus cover and closer
- JPEG only, 320–1440px wide, aspect ratio 0.80–1.91 (these cards are 0.80)
- 2,200 caption characters, 30 hashtags
