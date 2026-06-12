#!/bin/zsh
# Watchdog for the Jack app — keeps streamlit + ngrok + no-sleep alive on Darya's Mac.
# Launched by launchd (com.belovedpets.jackapp) at login; loops forever and restarts
# any piece that dies. KeepAlive on this Mac is unreliable, so the loop is the real guard.

APP_DIR="/Users/macbook/Databases/jack-app"
VENV="$APP_DIR/.venv/bin"
NGROK="$HOME/bin/ngrok"
DOMAIN="https://zipfile-henna-unmasking.ngrok-free.dev"
LOG="/tmp/jack_watchdog.log"

echo "$(date) watchdog started" >> "$LOG"

while true; do
  # 1) keep the Mac awake so the tunnel doesn't drop on sleep
  pgrep -x caffeinate >/dev/null 2>&1 || caffeinate -dimsu &

  # 2) streamlit on :8501
  if ! pgrep -f "streamlit run app.py" >/dev/null 2>&1; then
    echo "$(date) (re)starting streamlit" >> "$LOG"
    cd "$APP_DIR" && "$VENV/streamlit" run app.py \
      --server.headless true --browser.gatherUsageStats false \
      >> /tmp/streamlit_jack.log 2>&1 &
    sleep 6
  fi

  # 3) ngrok pinned to the permanent domain
  if ! pgrep -f "ngrok http 8501" >/dev/null 2>&1; then
    echo "$(date) (re)starting ngrok" >> "$LOG"
    "$NGROK" http 8501 --url "$DOMAIN" --log=stdout >> /tmp/ngrok_jack.log 2>&1 &
    sleep 4
  fi

  sleep 30
done
