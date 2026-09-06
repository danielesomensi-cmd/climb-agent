#!/usr/bin/env bash
# DEPRECATO 2026-09-06: il bridge di @Climbagent_bot ora è ~/Projects/cc-bridge
# (bots/climb.toml, launchd com.daniele.bridge-climb), che usa gli stessi file di
# stato di questo script (.claude_bridge_session, _outbox, _inbox) e lo stesso
# .env. Questo file resta per storico e per i test A276; non viene più eseguito.
# Gestione: ~/Projects/cc-bridge/bin/bots.sh status|restart climb|logs climb
#
# A277 — installa il Telegram bridge come LaunchAgent, così riparte da solo.
#
#   ./scripts/install_bridge_service.sh              installa e avvia
#   ./scripts/install_bridge_service.sh --uninstall  ferma e rimuove
#   ./scripts/install_bridge_service.sh --status     stato + ultime righe di log
#
# PERCHÉ: tmux + caffeinate tengono sveglio il Mac, ma NON fanno ripartire un
# processo caduto e non sopravvivono a un reboot. Con launchd il bridge riparte
# da solo dopo un crash e al login — che è la sola condizione in cui ha senso
# scrivergli da lontano.
#
# LIMITE DA CONOSCERE: è un LaunchAgent, non un LaunchDaemon. Gira nella sessione
# dell'utente, quindi il Mac deve restare **loggato** (non alla schermata di
# login). Un LaunchDaemon girerebbe da root senza sessione, ma non potrebbe
# leggere il portachiavi né le credenziali di Claude Code — quindi no.
#
# Restano vere le due condizioni di sempre: Mac attaccato alla corrente, e
# Impostazioni → Batteria → Alimentatore → "Impedisci lo stop automatico quando
# lo schermo è spento" attivo. launchd riavvia un processo morto, non risveglia
# un Mac addormentato.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
LABEL="app.climbagent.telegram-bridge"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$REPO_ROOT/.claude_bridge.log"
TARGET="gui/$(id -u)/$LABEL"

status() {
  echo "── stato ──────────────────────────────────────────"
  if launchctl print "$TARGET" >/dev/null 2>&1; then
    launchctl print "$TARGET" | grep -E "^\s+(state|pid|last exit code) " || true
  else
    echo "  servizio NON caricato"
  fi
  echo "  processi: $(pgrep -fc telegram_bridge.py 2>/dev/null || echo 0)"
  echo "── ultime righe di log ────────────────────────────"
  tail -8 "$LOG" 2>/dev/null || echo "  (nessun log)"
}

uninstall() {
  launchctl bootout "$TARGET" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✅ servizio rimosso. Il bridge non ripartirà più da solo."
}

case "${1:-}" in
  --status) status; exit 0 ;;
  --uninstall) uninstall; exit 0 ;;
  "") ;;
  *) echo "Opzione non riconosciuta: $1" >&2; exit 2 ;;
esac

# --- preflight: fallire qui è molto meglio che in un loop di riavvii ---------
PYTHON="$REPO_ROOT/.venv-bridge/bin/python"
[ -x "$PYTHON" ] || {
  echo "✗ manca $PYTHON" >&2
  echo "  python3 -m venv .venv-bridge && .venv-bridge/bin/pip install -r scripts/requirements-bridge.txt" >&2
  exit 1
}
for var in TELEGRAM_BRIDGE_TOKEN TELEGRAM_ALLOWED_CHAT_ID; do
  grep -q "^$var=" "$REPO_ROOT/.env" || { echo "✗ manca $var in .env" >&2; exit 1; }
done

# Un bridge avviato a mano terrebbe il token occupato: Telegram accetta un solo
# getUpdates per bot, e launchd finirebbe in un ciclo di riavvii falliti.
if tmux has-session -t bridge 2>/dev/null; then
  echo "• chiudo la sessione tmux 'bridge' (d'ora in poi ci pensa launchd)"
  tmux kill-session -t bridge
fi
pkill -f "telegram_bridge.py" 2>/dev/null && echo "• fermato un bridge avviato a mano" || true
sleep 1
rm -f "$REPO_ROOT/.claude_bridge.pid"

# --- plist -------------------------------------------------------------------
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <!-- caffeinate esce quando esce il figlio, quindi launchd sorveglia
         comunque il bridge: -dimsu impedisce lo sleep mentre gira. -->
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-dimsu</string>
        <string>$PYTHON</string>
        <string>$REPO_ROOT/scripts/telegram_bridge.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$REPO_ROOT</string>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <!-- Senza throttle un errore di configurazione diventa un ciclo di riavvii
         a piena velocità che riempie il log e nasconde la causa. -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <!-- launchd parte con un PATH minimo: senza questo non trova claude
         (~/.local/bin) né ffmpeg/whisper-cli (/opt/homebrew/bin), e i vocali
         fallirebbero solo da servizio, non quando lo lanci a mano. -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
PLIST_EOF

launchctl bootout "$TARGET" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "$TARGET" 2>/dev/null || true
sleep 4

echo "✅ installato: $PLIST"
status
