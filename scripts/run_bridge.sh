#!/usr/bin/env bash
# DEPRECATO 2026-09-06: il bridge di @Climbagent_bot ora è ~/Projects/cc-bridge
# (bots/climb.toml, launchd com.daniele.bridge-climb), che usa gli stessi file di
# stato di questo script (.claude_bridge_session, _outbox, _inbox) e lo stesso
# .env. Questo file resta per storico e per i test A276; non viene più eseguito.
# Gestione: ~/Projects/cc-bridge/bin/bots.sh status|restart climb|logs climb
#
# Avvia il Telegram → Claude Code bridge (A276) tenendo sveglio il Mac.
#
#   ./scripts/run_bridge.sh
#
# `caffeinate -dimsu` impedisce lo sleep finché il bridge gira:
#   -d display  -i idle  -m disco  -s sleep da alimentazione  -u utente attivo
#
# PERCHÉ CONTA: se il Mac si addormenta il bridge muore, il long polling si
# ferma e i messaggi mandati da Kalymnos non arrivano da nessuna parte.
# Servono DUE cose, non solo caffeinate:
#   1. il Mac deve restare COLLEGATO ALLA CORRENTE (a batteria macOS ignora
#      buona parte di caffeinate);
#   2. Impostazioni → Batteria → Alimentatore → "Impedisci lo stop automatico
#      quando lo schermo è spento" ATTIVO.
#
# MODO CONSIGLIATO: non lanciarlo a mano, installalo come servizio —
#   ./scripts/install_bridge_service.sh
# launchd lo riavvia dopo un crash e al login; tmux e caffeinate da soli non lo
# fanno. Questo script resta utile per una sessione in primo piano, per vedere
# il log scorrere mentre debuggi.
#
# Attenzione: se il servizio launchd è attivo, avviarlo anche qui fallisce (un
# solo getUpdates per token) — il lock su .claude_bridge.pid te lo dice.
#
# In alternativa, per farlo sopravvivere alla chiusura del terminale con tmux:
#   tmux new -s bridge './scripts/run_bridge.sh'
#   tmux attach -t bridge      # per riattaccarti
#   Ctrl-b d                   # per staccarti
#
# Follow-up possibile (non in A276): un plist launchd per farlo ripartire da
# solo al boot e dopo un crash.
#
# Setup, una volta sola:
#   python3 -m venv .venv-bridge
#   .venv-bridge/bin/pip install -r scripts/requirements-bridge.txt
#   # in .env: TELEGRAM_BRIDGE_TOKEN=... e TELEGRAM_ALLOWED_CHAT_ID=...
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${BRIDGE_PYTHON:-.venv-bridge/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "Interprete non trovato: $PYTHON" >&2
  echo "  python3 -m venv .venv-bridge" >&2
  echo "  .venv-bridge/bin/pip install -r scripts/requirements-bridge.txt" >&2
  exit 1
fi

exec caffeinate -dimsu "$PYTHON" scripts/telegram_bridge.py
