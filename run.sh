#!/usr/bin/env bash
# Launch the Algora agentic interview assistant.
#
# Serves HTTPS by default with a self-signed cert. HTTPS matters because the
# browser microphone (Web Speech API) only works in a SECURE CONTEXT — on an
# iPhone reached at http://<laptop-ip>:8000 that context is NOT secure, so the
# mic button can't appear. Over https:// (after accepting the cert once) it works.
#
#   ./run.sh            # HTTPS (recommended; mic works on iPhone)
#   HTTPS=0 ./run.sh    # plain HTTP (no cert warning; mic only on laptop/localhost)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv…"
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/python -m pip install -r requirements.txt
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -f ".env" ]; then
  set -a; . ./.env; set +a
fi
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set. Export it or put it in .env" >&2
  exit 1
fi

PORT="${PORT:-8000}"
HTTPS="${HTTPS:-1}"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
SSL_ARGS=()
SCHEME="http"

if [ "$HTTPS" = "1" ]; then
  CERT_DIR=".certs"; CERT="$CERT_DIR/cert.pem"; KEY="$CERT_DIR/key.pem"
  if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "Generating a self-signed certificate (one time)…"
    mkdir -p "$CERT_DIR"
    # Basic self-signed cert; SAN added when supported (harmless if not).
    if ! openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
         -keyout "$KEY" -out "$CERT" -subj "/CN=algora.local" \
         -addext "subjectAltName=DNS:localhost,IP:127.0.0.1${LAN_IP:+,IP:$LAN_IP}" 2>/dev/null; then
      openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
        -keyout "$KEY" -out "$CERT" -subj "/CN=algora.local" 2>/dev/null
    fi
  fi
  SSL_ARGS=(--ssl-keyfile "$KEY" --ssl-certfile "$CERT")
  SCHEME="https"
fi

echo "──────────────────────────────────────────────"
echo "  Algora starting (${SCHEME})…"
echo "  On this laptop:   ${SCHEME}://localhost:${PORT}"
if [ -n "${LAN_IP}" ]; then
  echo "  On your iPhone:   ${SCHEME}://${LAN_IP}:${PORT}"
fi
if [ "$HTTPS" = "1" ]; then
  echo ""
  echo "  NOTE: the cert is self-signed, so the browser shows a one-time warning."
  echo "  Laptop: click 'Advanced' → proceed.   iPhone Safari: tap 'Show Details'"
  echo "  → 'visit this website'. After that the mic works in all tabs."
fi
if [ "${RELOAD:-1}" = "1" ]; then
  echo "  Auto-reload: ON — backend code changes apply automatically (no manual restart)."
  echo "  (set RELOAD=0 to disable.)"
fi
echo "──────────────────────────────────────────────"

# Auto-reload on backend changes by default, so you never run stale code. Watch only
# backend/ — frontend files are served fresh from disk and just need a browser refresh.
RELOAD_ARGS=()
if [ "${RELOAD:-1}" = "1" ]; then
  RELOAD_ARGS=(--reload --reload-dir backend)
fi

exec ./.venv/bin/python -m uvicorn backend.server:app \
  --host 0.0.0.0 --port "${PORT}" "${SSL_ARGS[@]}" "${RELOAD_ARGS[@]}"
