#!/usr/bin/env bash
# Build (and optionally post) a day's carousel from a checkout.
#
#   ./scripts/run_local.sh                 # today in Panama, build only
#   ./scripts/run_local.sh 2026-09-12      # a specific day, build only
#   ./scripts/run_local.sh 2026-09-12 post # ...and publish it
#
# Build-only needs no credentials and touches no network, so it is the safe
# way to look at tomorrow's cards before the schedule does.
set -euo pipefail
cd "$(dirname "$0")/.."

DATE="${1:-$(TZ=America/Panama date +%F)}"
MODE="${2:-build}"
mkdir -p build

python3 scripts/select_today.py events.json --date "$DATE" --out build/today.json || {
  [ $? -eq 3 ] && { echo "No events on $DATE - nothing to post."; exit 0; }; exit 1; }

TX=(); [ -f tx.json ] && TX=(--tx tx.json)
python3 scripts/render_cards.py build/today.json --out "docs/$DATE" "${TX[@]}"
python3 scripts/build_caption.py build/today.json --out build/caption.txt "${TX[@]}"
python3 scripts/verify_post.py "docs/$DATE" --caption build/caption.txt

echo
echo "Cards:   docs/$DATE"
echo "Caption: build/caption.txt"

if [ "$MODE" = "post" ]; then
  : "${PAGES_BASE_URL:?set PAGES_BASE_URL, e.g. https://you.github.io/panamalive-daily}"
  echo; echo "Committing images so Instagram can fetch them..."
  git add "docs/$DATE" && git commit -qm "Carousel for $DATE" && git push
  python3 scripts/publish_instagram.py "docs/$DATE" \
    --caption build/caption.txt \
    --base-url "$PAGES_BASE_URL/$DATE" \
    --state "build/published-$DATE.json" \
    --wait-for-urls 300
fi
