# Working notes

A running handoff, newest first. The README says how the thing works; this
says what state it is in and what is half-finished.

---

## 2026-11-03

### The reel sizes and paces itself now

Three settings used to be fixed and are not any more. All of them live in
`scripts/build_reel.py`; the workflow passes none of them.

**Length follows the content.** It was 14 seconds whatever the day held, so a
36-event day scrolled nearly three times faster than a quiet one. The scroll
distance now sets the length, holding the *speed* steady at a peak of
`--px-per-sec 48` — about 2.1 seconds per row, which is average reading pace.
A 17-event day comes out around 59s.

**Type size follows the time budget.** `--zoom` is a **ceiling** (1.80), not a
value. Bigger type means a taller poster, and at a fixed pace a taller poster
means a longer reel — so the largest type would put a 65-event day past three
minutes. The builder measures the poster, checks it against `--max-seconds`,
and steps the type down only as far as it must, never below `--zoom-floor`
(1.20). Quiet days reach the ceiling; busy days come down and keep the pace.

**The call to action has its own space.** The poster is rendered with a strip
of blank canvas above the footer and the card is drawn into it, so it covers
no events. It also waits for the scroll to stop — it used to fade in 1.7s
early, over moving rows.

### Known gap: the busiest days still outrun the budget

65 events at the 1.20 floor is a 5,322px poster. Holding 2s per row across it
needs **113 seconds**, so it hits the 60s cap and scrolls at ~95 px/s instead
of 48. No type size fixes this — only a longer reel. Raising `--max-seconds`
to ~120 would close it (Instagram allows 3 minutes). Not done: it is a
judgement call about how long a reel anyone will watch.

### The footer could not survive a narrow canvas

`.foot` is one fixed-width row — wordmark left, handle right, `space-between`
— so it does not reflow, it overflows. Past about zoom 1.5 the handle ran off
the edge (`@thepanamalive.a`). Everything else on the poster is a vertical
stack that just grows taller, which is why only this bar broke. It is now
pinned to the size it has always had, so it renders identically at any zoom.
If you ever restyle the footer, re-check it at zoom 1.8.

### Captions carry the agenda

The caption opens with the full event list, grouped by category in the same
order the reel scrolls, each line with venue, time and price. Group by
category — do **not** break on each change of one: the selection is ordered by
priority, so the out-of-town rows trail the local ones and a naive loop
printed COMMUNITY twice with NIGHTLIFE in between.

Over 2,200 characters the last rows drop and a `+N more on PanamaLive.Ai` line
is appended. A reel caption still takes `--max-tags 5`.

### Buffer's composer eats the first thing you type

Posting by hand through publish.buffer.com: the editor silently swallows the
first chunk typed after it gets focus, and **the character counter keeps
counting the lost text**, so the count looks right while the text is gone.
This is what shipped the Oct 12 caption without its headline. Type the
headline, read it back, then type the rest. `ctrl+a` does not select inside
that editor.

### Open

* `--max-seconds` for the busiest days — see above.
* `docs/index.html` still redirects to **2026-10-03**. Each day's own page is
  fine; only the "newest day" root is stale, and has been for a month.
* `igopanama.com/panama-events-calendar` was proposed as a weekly source. It
  is **not** added: `pty-week` is a plugin and its folder is not reachable
  from a cloud session. Worth knowing before spending time on it — across
  Nov 3–4 it listed nothing the existing sources did not already have.
  `tourismpanama.com` is already in that source list and yields no dated
  events at all; its landing and category pages carry none.
* First unattended night with the sizing changes is **Nov 4**. If the morning
  post looks wrong, put `--zoom 1.45` back on the `build_reel.py` line in
  `.github/workflows/daily-post.yml` — that pins the old behaviour.
