"""A276 — Telegram → Claude Code bridge.

Copertura minima e mirata: il bridge è uno script locale, non codice di
prodotto, e non tocca né engine né API. I tre invarianti che contano davvero:

  1. allowlist — un chat id non autorizzato non produce NESSUNA chiamata in
     uscita e NESSUN subprocess (è l'unica cosa fra uno sconosciuto e una shell);
  2. chunking  — nessun blocco supera il cap 4096 di Telegram;
  3. sessione  — il session id ritornato viene scritto e riletto correttamente.

Il modulo vive in scripts/ (non è un package) e importa python-telegram-bot in
un try/except, così questi test girano nel venv del backend senza installarlo.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

BRIDGE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "telegram_bridge.py"


@pytest.fixture(scope="module")
def bridge():
    spec = importlib.util.spec_from_file_location("telegram_bridge_a276", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- allowlist

class _Recorder:
    """Registra ogni chiamata in uscita che il bridge tentasse di fare."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def reply_text(self, *args, **kwargs):
        self.calls.append("reply_text")

    async def send_message(self, *args, **kwargs):
        self.calls.append("send_message")

    async def send_document(self, *args, **kwargs):
        self.calls.append("send_document")

    async def send_chat_action(self, *args, **kwargs):
        self.calls.append("send_chat_action")


class _FakeChat:
    def __init__(self, chat_id: int, recorder: _Recorder) -> None:
        self.id = chat_id
        self._rec = recorder

    async def send_message(self, *a, **k):
        await self._rec.send_message(*a, **k)

    async def send_document(self, *a, **k):
        await self._rec.send_document(*a, **k)


class _FakeMessage:
    def __init__(self, text: str, recorder: _Recorder) -> None:
        self.text = text
        self._rec = recorder

    async def reply_text(self, *a, **k):
        await self._rec.reply_text(*a, **k)


class _FakeUser:
    id = 4242
    username = "sconosciuto"


class _FakeUpdate:
    def __init__(self, chat_id: int, text: str, recorder: _Recorder) -> None:
        self.effective_chat = _FakeChat(chat_id, recorder)
        self.effective_message = _FakeMessage(text, recorder)
        self.effective_user = _FakeUser()


class _FakeContext:
    def __init__(self, recorder: _Recorder) -> None:
        self.bot = recorder


ALLOWED = 7736751634


def _run_message(bridge, chat_id: int, monkeypatch):
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    spawned: list[str] = []

    async def _never(prompt):
        spawned.append(prompt)
        return "non dovrebbe succedere", "sid"

    monkeypatch.setattr(bridge, "run_claude", _never)
    # Il session id finto non deve MAI finire nel .claude_bridge_session vero:
    # è già successo una volta e ha rotto il resume del bridge reale.
    saved: list[str] = []
    monkeypatch.setattr(bridge, "save_session_id", lambda sid, *a, **k: saved.append(sid))

    update = _FakeUpdate(chat_id, "cat backend/data/user_state.json", recorder)
    asyncio.run(bridge.on_message(update, _FakeContext(recorder)))
    return recorder, spawned


def test_allowlist_blocca_chat_estranea(bridge, monkeypatch):
    """Chat non autorizzata: zero risposte (silenzio, non un errore) e zero subprocess."""
    recorder, spawned = _run_message(bridge, chat_id=999_000_111, monkeypatch=monkeypatch)
    assert recorder.calls == []
    assert spawned == []


def test_allowlist_lascia_passare_la_chat_autorizzata(bridge, monkeypatch):
    """Controprova: senza questa, il test sopra passerebbe anche con on_message rotta."""
    recorder, spawned = _run_message(bridge, chat_id=ALLOWED, monkeypatch=monkeypatch)
    assert spawned == ["cat backend/data/user_state.json"]
    assert "send_message" in recorder.calls


def test_comandi_rifiutano_chat_estranea(bridge):
    """/status e /new non devono rispondere né agire per una chat non autorizzata."""
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)
    recorder = _Recorder()
    update = _FakeUpdate(999_000_111, "/status", recorder)
    for handler in (bridge.cmd_status, bridge.cmd_new, bridge.cmd_stop, bridge.cmd_help):
        asyncio.run(handler(update, _FakeContext(recorder)))
    assert recorder.calls == []


# ----------------------------------------------------------------- chunking

def test_chunking_rispetta_il_cap_telegram(bridge):
    text = "\n".join(f"riga {i}: " + "x" * 100 for i in range(120))
    assert len(text) > 12_000

    chunks = bridge.split_message(text)

    assert chunks, "una stringa da 12k deve produrre almeno un chunk"
    assert all(len(c) <= bridge.CHUNK_LIMIT for c in chunks)
    assert all(len(c) <= 4096 for c in chunks), "cap duro dell'API Telegram"
    assert "\n".join(chunks) == text, "nessun contenuto perso o duplicato"


def test_chunking_spezza_una_riga_singola_gigante(bridge):
    """Una riga senza a capo più lunga del cap va tagliata a forza, non spedita intera."""
    chunks = bridge.split_message("y" * 12_000)
    assert all(len(c) <= bridge.CHUNK_LIMIT for c in chunks)
    assert "".join(chunks) == "y" * 12_000


def test_chunking_stringa_vuota(bridge):
    assert bridge.split_message("") == []


# ---------------------------------------------------------------- sessione

def test_session_id_scritto_e_riletto(bridge, tmp_path):
    path = tmp_path / ".claude_bridge_session"

    assert bridge.load_session_id(path) is None

    bridge.save_session_id("291441ec-dbb3-4cdd-8c7a-24be3e7006e9", path)
    assert bridge.load_session_id(path) == "291441ec-dbb3-4cdd-8c7a-24be3e7006e9"

    assert bridge.clear_session_id(path) is True
    assert bridge.load_session_id(path) is None
    assert bridge.clear_session_id(path) is False


def test_parse_result_estrae_testo_e_session_id(bridge):
    payload = json.dumps({
        "is_error": False,
        "subtype": "success",
        "session_id": "291441ec-dbb3-4cdd-8c7a-24be3e7006e9",
        "result": "PONG",
    })
    assert bridge.parse_claude_result(payload) == (
        "PONG", "291441ec-dbb3-4cdd-8c7a-24be3e7006e9",
    )


def test_parse_result_su_errore_conserva_il_session_id(bridge):
    """Una sessione nata e poi fallita resta riusabile: un boot a freddo costa."""
    payload = json.dumps({
        "is_error": True,
        "subtype": "error_during_execution",
        "session_id": "abc123",
        "result": "boom",
    })
    with pytest.raises(bridge.BridgeError) as excinfo:
        bridge.parse_claude_result(payload)
    assert excinfo.value.session_id == "abc123"


def test_parse_result_su_output_non_json(bridge):
    with pytest.raises(bridge.BridgeError):
        bridge.parse_claude_result("Traceback (most recent call last): ...")


def test_argv_include_resume_solo_con_sessione(bridge):
    fresh = bridge.build_claude_argv("ciao", None)
    assert "--resume" not in fresh
    assert fresh[1:3] == ["-p", "ciao"]
    assert "--output-format" in fresh and "json" in fresh
    assert "--dangerously-skip-permissions" in fresh
    assert fresh[fresh.index("--model") + 1] == "sonnet"

    resumed = bridge.build_claude_argv("ciao", "sid-1")
    assert resumed[resumed.index("--resume") + 1] == "sid-1"


# ------------------------------------------------- recupero sessione stantia

def test_sessione_stantia_viene_buttata_e_il_comando_ritentato(bridge, monkeypatch, tmp_path):
    """`--resume` su una sessione sparita non deve bloccare il bridge per sempre.

    Senza questo recupero, da Kalymnos ogni messaggio riceverebbe lo stesso
    errore e non ci sarebbe modo di uscirne se non /new.
    """
    path = tmp_path / ".claude_bridge_session"
    bridge.save_session_id("sessione-morta", path)
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    monkeypatch.setattr(
        bridge, "load_session_id",
        lambda *a, **k: path.read_text().strip() if path.exists() else None,
    )
    monkeypatch.setattr(
        bridge, "clear_session_id",
        lambda *a, **k: (path.unlink(missing_ok=True), True)[1],
    )

    tentativi: list[str | None] = []

    async def _fake_once(prompt, session_id):
        tentativi.append(session_id)
        if session_id:
            raise bridge.BridgeError(
                'claude è uscito con codice 1.\nError: --resume requires a valid session ID'
            )
        return "ok", "sessione-nuova"

    monkeypatch.setattr(bridge, "_run_claude_once", _fake_once)

    text, session_id = asyncio.run(bridge.run_claude("ciao"))

    assert tentativi == ["sessione-morta", None], "un solo ritentativo, da zero"
    assert (text, session_id) == ("ok", "sessione-nuova")
    assert not path.exists(), "la sessione morta va cancellata"


def test_errore_non_di_sessione_non_viene_ritentato(bridge, monkeypatch, tmp_path):
    """Un timeout o uno /stop non devono far ripartire il comando da capo."""
    path = tmp_path / ".claude_bridge_session"
    bridge.save_session_id("sessione-viva", path)
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)
    monkeypatch.setattr(bridge, "load_session_id", lambda *a, **k: (path.read_text().strip() if path.exists() else None))

    tentativi: list[str | None] = []

    async def _fake_once(prompt, session_id):
        tentativi.append(session_id)
        raise bridge.BridgeError("Timeout dopo 15 minuti — processo ucciso.")

    monkeypatch.setattr(bridge, "_run_claude_once", _fake_once)

    with pytest.raises(bridge.BridgeError):
        asyncio.run(bridge.run_claude("ciao"))
    assert tentativi == ["sessione-viva"], "nessun ritentativo"
    assert path.exists(), "la sessione valida non va cancellata"
