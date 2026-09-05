#!/usr/bin/env bash
#
# One command from a clean checkout to a spoken video spec.
#
#   ./scripts/setup-mac.sh                 # topic defaults to dehydration
#   ./scripts/setup-mac.sh "vitamin d"
#
# Idempotent: run it again after a pull and it reuses everything already there.
# It exists because the five commands it replaces each have a way to fail late —
# the wrong Python builds a venv that only breaks at `pip install kokoro`, and a
# missing espeak-ng only shows up on a word the phonemiser has never seen.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/.venv"
TOPIC="${1:-dehydration}"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }

cd "$REPO"

# --- 1. latest main -------------------------------------------------------

say "Updating from main"
if [ -n "$(git status --porcelain)" ]; then
  warn "working tree has local changes — skipping the pull so nothing of yours is lost"
elif git pull --ff-only origin main >/dev/null 2>&1; then
  ok "$(git log --oneline -1)"
else
  warn "could not fast-forward to origin/main; continuing with what is checked out"
fi

# --- 2. an interpreter the ML stack will actually install on --------------

say "Python"
# kokoro and whisperx both pin python <3.14. Ved's default is 3.14, and the
# failure lands at pip install time, minutes in, not at venv creation.
PYTHON=""
for candidate in python3.12 python3.13 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
done

if [ -x "$VENV/bin/python" ]; then
  existing="$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  case "$existing" in
    3.11|3.12|3.13) ok ".venv already on Python $existing" ;;
    *)
      warn ".venv is on Python $existing, which kokoro and whisperx refuse to install on."
      warn "Remove it and re-run:  rm -rf \"$VENV\" && ./scripts/setup-mac.sh"
      exit 1
      ;;
  esac
elif [ -z "$PYTHON" ]; then
  if command -v brew >/dev/null 2>&1; then
    say "Installing Python 3.12 (nothing older than 3.11 or newer than 3.13 works here)"
    brew install python@3.12
    PYTHON="$(brew --prefix)/opt/python@3.12/bin/python3.12"
  else
    warn "No Python 3.11–3.13 and no Homebrew. Install one, then re-run."
    exit 1
  fi
fi

if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
  ok "created .venv on $("$VENV/bin/python" -V)"
fi

"$VENV/bin/python" -m pip install --quiet --upgrade pip setuptools wheel
"$VENV/bin/pip" install --quiet -e "$REPO[dev]"
ok "content layer installed"

# --- 3. phonemiser --------------------------------------------------------

say "espeak-ng"
if command -v espeak-ng >/dev/null 2>&1; then
  ok "already present"
elif command -v brew >/dev/null 2>&1; then
  brew install espeak-ng
else
  warn "not installed and no Homebrew — Kokoro will still run, but words its"
  warn "dictionary has never seen get a worse pronunciation"
fi

# --- 4. the voice ---------------------------------------------------------

say "Kokoro"
if "$VENV/bin/python" -c "import kokoro" >/dev/null 2>&1; then
  ok "already installed"
else
  warn "first install pulls torch — a few hundred MB, several minutes"
  "$VENV/bin/pip" install --quiet kokoro soundfile
  ok "installed"
fi

# --- 5. prove it ----------------------------------------------------------

say "Running the pipeline on: $TOPIC"
if [ ! -d "$HOME/.cache/huggingface/hub/models--hexgrad--Kokoro-82M" ]; then
  warn "first run downloads ~330 MB of Kokoro weights; later runs are offline"
fi
"$VENV/bin/videobot" --topic "$TOPIC" --voice kokoro

say "Done"
cat <<EOF
  Listen to the voiceover:   afplay \$(ls -t "$REPO"/.cache/voice/*.wav | head -1)
  Run one more topic:        "$VENV/bin/videobot" --topic "sleep" --voice kokoro
  Work in the venv:          source "$VENV/bin/activate"

  Make the shortcut permanent (an \`alias\` typed at a prompt dies with the window):
    echo 'alias vb="cd $REPO && source .venv/bin/activate"' >> ~/.zshrc
EOF
