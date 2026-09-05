#!/usr/bin/env bash
#
# Topic in, MP4 out. One command, from a cold machine.
#
#   ./scripts/make-video.sh "dehydration"
#   ./scripts/make-video.sh "dehydration" --scale 0.5 --seconds 6   # fast preview
#
# Everything after the topic is passed through to the renderer.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/.venv"
TOPIC="${1:-dehydration}"
shift || true

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }

# --- content layer: topic -> scene-spec.json ------------------------------

"$REPO/scripts/setup-mac.sh" "$TOPIC"

SLUG="$("$VENV/bin/python" -c 'import sys; from videobot.cli import slugify; print(slugify(sys.argv[1]))' "$TOPIC")"
SPEC="$REPO/output/$SLUG/scene-spec.json"
[ -f "$SPEC" ] || { warn "no spec at $SPEC"; exit 1; }

# --- motion layer: scene-spec.json -> MP4 ---------------------------------

say "Motion layer"
command -v node >/dev/null 2>&1 || { warn "node not found — install Node 20+ (brew install node)"; exit 1; }
ok "node $(node -v)"

cd "$REPO/motion"
if [ ! -d node_modules ]; then
  warn "first run installs the motion dependencies and a headless browser"
  npm install
else
  ok "dependencies present"
fi

# node_modules can be present while the browser is not. Playwright downloads
# browsers outside npm — into ~/Library/Caches/ms-playwright — so an npm install
# that ran before a Playwright version bump leaves node_modules complete and the
# browser missing. The only reliable check is to launch one, the same way the
# renderer does, rather than to look for a file.
say "Headless browser"
if node --input-type=module -e "
import { chromium } from 'playwright';
import { existsSync } from 'node:fs';
const path = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';
const browser = await chromium.launch({
  executablePath: existsSync(path) ? path : undefined,
  args: ['--no-sandbox', '--use-gl=swiftshader'],
});
await browser.close();
" >/dev/null 2>&1; then
  ok "launches"
else
  warn "downloading Chromium (~150 MB, once)"
  npx --yes playwright install chromium
fi

node scripts/prepare-data.mjs "$SPEC"
node scripts/render.mjs "$@"

say "Done"
MP4="$(ls -t "$REPO"/output/"$SLUG"/*.mp4 2>/dev/null | head -1 || true)"
if [ -n "$MP4" ]; then
  printf '  %s\n' "$MP4"
  printf '  open it:  open "%s"\n' "$MP4"
else
  warn "the renderer reported no MP4 — see the output above"
  exit 1
fi
