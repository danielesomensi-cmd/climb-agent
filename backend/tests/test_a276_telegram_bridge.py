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
import sys
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

def _now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


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

    async def send_photo(self, *args, **kwargs):
        self.calls.append("send_photo")

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

    async def send_photo(self, *a, **k):
        await self._rec.send_photo(*a, **k)


class _FakeMessage:
    def __init__(self, text: str, recorder: _Recorder) -> None:
        self.text = text
        # Ogni messaggio Telegram vero porta una data, ed è quella che decide se
        # è arrivato mentre il bridge era giù: i double devono averla.
        self.date = _now_utc()
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
    # B348: il modello del bridge e' una costante di configurazione
    # (`telegram_bridge.MODEL`), non un valore che questo test debba fissare:
    # cambiarla faceva fallire un test che verifica la FORMA degli argomenti,
    # non quale modello sia in uso. Asserisce sul valore vero, cosi' il prossimo
    # cambio di modello non rompe nulla.
    assert fresh[fresh.index("--model") + 1] == bridge.MODEL

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


# ------------------------------------------------------- trascrizione vocali

def test_ffmpeg_argv_converte_a_16k_mono_pcm(bridge):
    argv = bridge.build_ffmpeg_argv(Path("/tmp/in.ogg"), Path("/tmp/out.wav"))
    assert argv[-1] == "/tmp/out.wav"
    assert argv[argv.index("-i") + 1] == "/tmp/in.ogg"
    assert argv[argv.index("-ar") + 1] == "16000"
    assert argv[argv.index("-ac") + 1] == "1"


def test_whisper_argv_include_lingua_modello_e_file(bridge, monkeypatch):
    monkeypatch.setenv("WHISPER_LANGUAGE", "it")
    argv = bridge.build_whisper_argv(Path("/tmp/audio.wav"), Path("/tmp/out"))
    assert argv[argv.index("-l") + 1] == "it"
    assert argv[argv.index("-f") + 1] == "/tmp/audio.wav"
    assert argv[argv.index("-of") + 1] == "/tmp/out"
    assert "-otxt" in argv


def test_transcribe_voice_senza_modello_da_errore_azionabile(bridge, monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "whisper_model_path", lambda: tmp_path / "non-esiste.bin")
    with pytest.raises(bridge.BridgeError, match="Modello whisper mancante"):
        asyncio.run(bridge.transcribe_voice(tmp_path / "voice.ogg"))


def test_transcribe_voice_senza_ffmpeg_da_errore_azionabile(bridge, monkeypatch, tmp_path):
    model = tmp_path / "model.bin"
    model.write_bytes(b"x")
    monkeypatch.setattr(bridge, "whisper_model_path", lambda: model)
    monkeypatch.setattr(bridge, "ffmpeg_binary", lambda: str(tmp_path / "non-esiste-ffmpeg"))
    with pytest.raises(bridge.BridgeError, match="ffmpeg non trovato"):
        asyncio.run(bridge.transcribe_voice(tmp_path / "voice.ogg"))


def test_transcribe_voice_senza_whisper_cli_da_errore_azionabile(bridge, monkeypatch, tmp_path):
    model = tmp_path / "model.bin"
    model.write_bytes(b"x")
    monkeypatch.setattr(bridge, "whisper_model_path", lambda: model)
    monkeypatch.setattr(bridge, "ffmpeg_binary", lambda: sys.executable)
    monkeypatch.setattr(bridge, "whisper_cli_binary", lambda: str(tmp_path / "non-esiste-whisper"))
    with pytest.raises(bridge.BridgeError, match="whisper-cli non trovato"):
        asyncio.run(bridge.transcribe_voice(tmp_path / "voice.ogg"))


def _stub_binaries(bridge, monkeypatch, tmp_path):
    model = tmp_path / "model.bin"
    model.write_bytes(b"x")
    monkeypatch.setattr(bridge, "whisper_model_path", lambda: model)
    monkeypatch.setattr(bridge, "ffmpeg_binary", lambda: sys.executable)
    monkeypatch.setattr(bridge, "whisper_cli_binary", lambda: sys.executable)


def test_transcribe_voice_flusso_completo(bridge, monkeypatch, tmp_path):
    """ffmpeg e whisper-cli sono finti (mai lanciati davvero): verifica solo
    che transcribe_voice sappia orchestrare argv → subprocess → lettura file."""
    _stub_binaries(bridge, monkeypatch, tmp_path)

    async def _fake_run_subprocess(argv, timeout):
        if "-otxt" in argv:
            out_base = Path(argv[argv.index("-of") + 1])
            out_base.with_suffix(".txt").write_text("ciao mondo\n", encoding="utf-8")
        else:
            Path(argv[-1]).write_bytes(b"RIFF....WAVEfmt ")
        return (0, "", "")

    monkeypatch.setattr(bridge, "_run_subprocess", _fake_run_subprocess)

    text = asyncio.run(bridge.transcribe_voice(tmp_path / "voice.ogg"))
    assert text == "ciao mondo"


def test_transcribe_voice_vuota_da_errore(bridge, monkeypatch, tmp_path):
    """Audio silenzioso: whisper esce 0 ma produce un .txt vuoto — non deve
    diventare un prompt vuoto passato a Claude."""
    _stub_binaries(bridge, monkeypatch, tmp_path)

    async def _fake_run_subprocess(argv, timeout):
        if "-otxt" in argv:
            out_base = Path(argv[argv.index("-of") + 1])
            out_base.with_suffix(".txt").write_text("   \n", encoding="utf-8")
        else:
            Path(argv[-1]).write_bytes(b"RIFF....WAVEfmt ")
        return (0, "", "")

    monkeypatch.setattr(bridge, "_run_subprocess", _fake_run_subprocess)

    with pytest.raises(bridge.BridgeError, match="Trascrizione vuota"):
        asyncio.run(bridge.transcribe_voice(tmp_path / "voice.ogg"))


def test_transcribe_voice_ffmpeg_fallito_da_errore(bridge, monkeypatch, tmp_path):
    _stub_binaries(bridge, monkeypatch, tmp_path)

    async def _fake_run_subprocess(argv, timeout):
        return (1, "", "errore di conversione")

    monkeypatch.setattr(bridge, "_run_subprocess", _fake_run_subprocess)

    with pytest.raises(bridge.BridgeError, match="Conversione audio fallita"):
        asyncio.run(bridge.transcribe_voice(tmp_path / "voice.ogg"))


# --------------------------------------------------------- handler on_voice

class _FakeTGFile:
    def __init__(self, recorder: _Recorder) -> None:
        self._rec = recorder

    async def download_to_drive(self, custom_path=None):
        self._rec.calls.append("download_to_drive")
        if custom_path:
            Path(custom_path).parent.mkdir(parents=True, exist_ok=True)
            Path(custom_path).write_bytes(b"fake")


class _FakeVoice:
    def __init__(self, recorder: _Recorder, file_size: int = 1000) -> None:
        self._rec = recorder
        self.file_id = "voice-123"
        self.file_size = file_size

    async def get_file(self):
        self._rec.calls.append("get_file")
        return _FakeTGFile(self._rec)


class _FakeVoiceMessage(_FakeMessage):
    def __init__(self, recorder: _Recorder, file_size: int = 1000) -> None:
        super().__init__("", recorder)
        self.voice = _FakeVoice(recorder, file_size)
        self.audio = None


class _FakeVoiceUpdate:
    def __init__(self, chat_id: int, recorder: _Recorder, file_size: int = 1000) -> None:
        self.effective_chat = _FakeChat(chat_id, recorder)
        self.effective_message = _FakeVoiceMessage(recorder, file_size)
        self.effective_user = _FakeUser()


def test_allowlist_blocca_voce_di_chat_estranea(bridge):
    """Come per il testo: chat non autorizzata → zero chiamate, niente download."""
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)
    update = _FakeVoiceUpdate(999_000_111, recorder)
    asyncio.run(bridge.on_voice(update, _FakeContext(recorder)))
    assert recorder.calls == []


def test_voce_troppo_grande_viene_rifiutata_senza_scaricare(bridge, monkeypatch):
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    async def _non_deve_essere_chiamata(*a, **k):
        raise AssertionError("un vocale oltre il limite non deve essere trascritto")

    monkeypatch.setattr(bridge, "transcribe_voice", _non_deve_essere_chiamata)

    update = _FakeVoiceUpdate(ALLOWED, recorder, file_size=bridge.VOICE_MAX_BYTES + 1)
    asyncio.run(bridge.on_voice(update, _FakeContext(recorder)))

    assert recorder.calls == ["reply_text"]


def test_voce_trascritta_ed_eseguita_per_chat_autorizzata(bridge, monkeypatch):
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    async def _fake_transcribe(src_path):
        return "controlla lo stato dei test"

    monkeypatch.setattr(bridge, "transcribe_voice", _fake_transcribe)

    spawned: list[str] = []

    async def _fake_run_claude(prompt):
        spawned.append(prompt)
        return "fatto", "sid-voice"

    monkeypatch.setattr(bridge, "run_claude", _fake_run_claude)
    saved: list[str] = []
    monkeypatch.setattr(bridge, "save_session_id", lambda sid, *a, **k: saved.append(sid))

    update = _FakeVoiceUpdate(ALLOWED, recorder)
    asyncio.run(bridge.on_voice(update, _FakeContext(recorder)))

    assert recorder.calls == ["get_file", "download_to_drive", "reply_text", "send_message"]
    assert spawned == ["controlla lo stato dei test"]
    assert saved == ["sid-voice"]


def test_voce_con_trascrizione_fallita_non_chiama_claude(bridge, monkeypatch):
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    async def _fake_transcribe(src_path):
        raise bridge.BridgeError("whisper-cli non trovato — installa con `brew install whisper-cpp`.")

    monkeypatch.setattr(bridge, "transcribe_voice", _fake_transcribe)

    spawned: list[str] = []

    async def _non_deve_essere_chiamata(prompt):
        spawned.append(prompt)
        return "non dovrebbe succedere", None

    monkeypatch.setattr(bridge, "run_claude", _non_deve_essere_chiamata)

    update = _FakeVoiceUpdate(ALLOWED, recorder)
    asyncio.run(bridge.on_voice(update, _FakeContext(recorder)))

    assert spawned == []
    assert "send_message" in recorder.calls  # deliver() dell'errore


# --------------------------------------------------------- handler on_photo (A280)

class _FakePhoto:
    def __init__(self, recorder: _Recorder, file_size: int = 1000) -> None:
        self._rec = recorder
        self.file_id = "photo-123"
        self.file_size = file_size

    async def get_file(self):
        self._rec.calls.append("get_file")
        return _FakeTGFile(self._rec)


class _FakePhotoMessage(_FakeMessage):
    def __init__(
        self, recorder: _Recorder, file_size: int = 1000,
        caption: str | None = None, message_id: int = 555,
    ) -> None:
        super().__init__("", recorder)
        self.photo = [_FakePhoto(recorder, file_size)]  # solo l'ultima (risoluzione più alta) conta
        self.caption = caption
        self.message_id = message_id


class _FakePhotoUpdate:
    def __init__(
        self, chat_id: int, recorder: _Recorder,
        file_size: int = 1000, caption: str | None = None,
    ) -> None:
        self.effective_chat = _FakeChat(chat_id, recorder)
        self.effective_message = _FakePhotoMessage(recorder, file_size, caption)
        self.effective_user = _FakeUser()


def test_allowlist_blocca_foto_di_chat_estranea(bridge):
    """Come per testo e voce: chat non autorizzata → zero chiamate, niente download."""
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)
    update = _FakePhotoUpdate(999_000_111, recorder)
    asyncio.run(bridge.on_photo(update, _FakeContext(recorder)))
    assert recorder.calls == []


def test_foto_troppo_grande_viene_rifiutata_senza_scaricare(bridge, monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "INBOX_DIR", tmp_path / "inbox")
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    update = _FakePhotoUpdate(ALLOWED, recorder, file_size=bridge.VOICE_MAX_BYTES + 1)
    asyncio.run(bridge.on_photo(update, _FakeContext(recorder)))

    assert recorder.calls == ["reply_text"]
    assert not (tmp_path / "inbox").exists()


def test_foto_scaricata_resta_leggibile_durante_il_turno_e_poi_cancellata(bridge, monkeypatch, tmp_path):
    """Il punto di tutta la feature: il file deve esistere ancora mentre
    Claude Code gira (per poterlo Read), e sparire subito dopo — INBOX_DIR
    non è un archivio."""
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(bridge, "INBOX_DIR", inbox)
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)
    expected_path = inbox / "555.jpg"

    spawned: list[str] = []

    async def _fake_run_claude(prompt):
        spawned.append(prompt)
        assert expected_path.exists(), "il file deve esistere mentre Claude Code lo legge"
        return "fatto", "sid-photo"

    monkeypatch.setattr(bridge, "run_claude", _fake_run_claude)
    saved: list[str] = []
    monkeypatch.setattr(bridge, "save_session_id", lambda sid, *a, **k: saved.append(sid))

    update = _FakePhotoUpdate(ALLOWED, recorder, caption="Snake Valley oggi")
    asyncio.run(bridge.on_photo(update, _FakeContext(recorder)))

    assert recorder.calls == ["get_file", "download_to_drive", "send_message"]
    assert str(expected_path) in spawned[0]
    assert "Snake Valley oggi" in spawned[0]
    assert saved == ["sid-photo"]
    assert not expected_path.exists(), "il file va cancellato a fine turno"


def test_foto_senza_didascalia_non_aggiunge_sezione_vuota(bridge, monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "INBOX_DIR", tmp_path / "inbox")
    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    spawned: list[str] = []

    async def _fake_run_claude(prompt):
        spawned.append(prompt)
        return "fatto", "sid"

    monkeypatch.setattr(bridge, "run_claude", _fake_run_claude)
    monkeypatch.setattr(bridge, "save_session_id", lambda *a, **k: None)

    update = _FakePhotoUpdate(ALLOWED, recorder, caption=None)
    asyncio.run(bridge.on_photo(update, _FakeContext(recorder)))

    assert "Didascalia" not in spawned[0]


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


# --------------------------------------------- messaggi arrivati a bridge giù

def test_messaggio_recente_non_e_stantio(bridge):
    from datetime import datetime, timedelta, timezone
    adesso = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert bridge.is_stale(adesso) is False


def test_messaggio_vecchio_e_stantio(bridge):
    from datetime import datetime, timedelta, timezone
    vecchio = datetime.now(timezone.utc) - timedelta(minutes=40)
    assert bridge.is_stale(vecchio) is True


def test_data_naive_trattata_come_utc(bridge):
    """Telegram manda date aware, ma una naive non deve far esplodere il confronto."""
    from datetime import datetime, timedelta
    naive = datetime.utcnow() - timedelta(seconds=10)
    assert bridge.is_stale(naive) is False


def test_data_assente_non_e_stantia(bridge):
    assert bridge.is_stale(None) is False


def test_messaggio_stantio_non_viene_eseguito_ma_viene_annunciato(bridge, monkeypatch):
    """La coda NON viene più buttata al riavvio, quindi un messaggio vecchio
    arriva davvero: va segnalato, non eseguito di nascosto ore dopo."""
    from datetime import datetime, timedelta, timezone

    recorder = _Recorder()
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    eseguiti: list[str] = []

    async def _mai(update, context, prompt):
        eseguiti.append(prompt)

    monkeypatch.setattr(bridge, "_execute_and_deliver", _mai)

    update = _FakeUpdate(ALLOWED, "cancella tutto", recorder)
    update.effective_message.date = datetime.now(timezone.utc) - timedelta(hours=3)

    asyncio.run(bridge.on_message(update, _FakeContext(recorder)))

    assert eseguiti == [], "un messaggio di 3 ore fa non va eseguito a sorpresa"
    assert recorder.calls == ["reply_text"], "ma l'utente deve saperlo"


# ------------------------------------------------------------ outbox (A277)

def test_deliver_outbox_senza_cartella_e_un_noop(bridge, tmp_path, monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(bridge, "OUTBOX_DIR", tmp_path / "non-esiste")
    update = _FakeUpdate(ALLOWED, "x", recorder)
    asyncio.run(bridge.deliver_outbox(update))
    assert recorder.calls == []


def test_deliver_outbox_manda_immagine_come_foto_e_la_cancella(bridge, tmp_path, monkeypatch):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "schizzo.png").write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(bridge, "OUTBOX_DIR", outbox)

    recorder = _Recorder()
    update = _FakeUpdate(ALLOWED, "x", recorder)
    asyncio.run(bridge.deliver_outbox(update))

    assert recorder.calls == ["send_photo"]
    assert not (outbox / "schizzo.png").exists()


def test_deliver_outbox_manda_non_immagine_come_documento(bridge, tmp_path, monkeypatch):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "dati.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bridge, "OUTBOX_DIR", outbox)

    recorder = _Recorder()
    update = _FakeUpdate(ALLOWED, "x", recorder)
    asyncio.run(bridge.deliver_outbox(update))

    assert recorder.calls == ["send_document"]
    assert not (outbox / "dati.json").exists()


def test_deliver_outbox_svuota_anche_se_il_send_fallisce(bridge, tmp_path, monkeypatch):
    """Un file che non riesce a partire non deve restare lì per sempre e
    ripresentarsi (e magari fallire di nuovo) al turno successivo."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "rotto.png").write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(bridge, "OUTBOX_DIR", outbox)

    class _FailingChat:
        async def send_photo(self, *a, **k):
            raise RuntimeError("rete giù")

    class _FakeUpdateFallito:
        effective_chat = _FailingChat()

    asyncio.run(bridge.deliver_outbox(_FakeUpdateFallito()))
    assert not (outbox / "rotto.png").exists()


def test_startup_flush_manda_outbox_senza_aspettare_un_messaggio(bridge, tmp_path, monkeypatch):
    """post_init: un'outbox rimasta piena da un riavvio va consegnata subito,
    non solo alla prossima volta che arriva un messaggio."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "schizzo.png").write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(bridge, "OUTBOX_DIR", outbox)
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    calls = []

    class _FakeBot:
        async def send_photo(self, chat_id, photo, caption=None):
            calls.append(("send_photo", chat_id))

        async def send_document(self, chat_id, document, filename=None):
            calls.append(("send_document", chat_id))

    class _FakeApplication:
        bot = _FakeBot()

    asyncio.run(bridge._startup_flush_outbox(_FakeApplication()))

    assert calls == [("send_photo", ALLOWED)]
    assert not (outbox / "schizzo.png").exists()


def test_startup_flush_senza_outbox_non_chiama_il_bot(bridge, tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "OUTBOX_DIR", tmp_path / "non-esiste")
    bridge.STATE = bridge.BridgeState(allowed_chat_id=ALLOWED)

    class _FailingBot:
        async def send_photo(self, *a, **k):
            raise AssertionError("non deve essere chiamato: outbox vuota")

    class _FakeApplication:
        bot = _FailingBot()

    asyncio.run(bridge._startup_flush_outbox(_FakeApplication()))
