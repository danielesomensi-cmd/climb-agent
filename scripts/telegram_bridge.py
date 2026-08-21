#!/usr/bin/env python3
"""Telegram → Claude Code bridge (A276) — strumento personale, locale.

Pilota una sessione Claude Code persistente sul repo climb-agent da Telegram,
al posto di SSH via Terminus da iPhone. Daniele scrive un messaggio, Claude Code
lo esegue nel repo, la risposta torna in chat.

NON è una feature di prodotto: non è esposta agli utenti, non va su Railway né
su Vercel, non importa nulla di `backend/`.

Vocali: un messaggio voice/audio viene scaricato, convertito con ffmpeg e
trascritto in locale con whisper.cpp (nessun audio lascia il Mac). Richiede
`ffmpeg` (`brew install ffmpeg`) e `whisper-cpp` (`brew install whisper-cpp`)
più un modello GGML — vedi `whisper_model_path()`. Se manca uno dei due il
bot risponde con l'errore invece di ignorare il vocale in silenzio.

Config (in `.env` alla root del repo, gitignored):

    TELEGRAM_BRIDGE_TOKEN      token di @Climbagent_bot (@BotFather)
    TELEGRAM_ALLOWED_CHAT_ID   unico chat id autorizzato (intero)

Config opzionale per la trascrizione (default sensati se omessa):

    WHISPER_MODEL_PATH   default ~/.claude/models/ggml-large-v3-turbo.bin
    WHISPER_CLI_BIN       default: whisper-cli nel PATH, poi /opt/homebrew/bin/whisper-cli
    WHISPER_LANGUAGE      default "it"
    FFMPEG_BIN             default: ffmpeg nel PATH, poi /opt/homebrew/bin/ffmpeg

Il nome `TELEGRAM_BRIDGE_TOKEN` è volutamente diverso da `TELEGRAM_BOT_TOKEN`,
che appartiene a un altro bot (founder alerts, `backend/api/notifications.py`):
riusare quel nome romperebbe le notifiche di produzione.

Sicurezza — il token è di fatto pubblico: chiunque trovi il bot può scrivergli, e
questo ponte esegue comandi con shell su una macchina personale. L'allowlist è
l'unica cosa fra uno sconosciuto e una shell. Ogni handler la controlla per
primo e, se il chat id non torna, **non risponde**: silenzio, non un errore, per
non confermare a un estraneo che il bot è vivo.

Trasporto: long polling (`getUpdates`). Nessun webhook — il Mac è dietro NAT, e
polling non richiede URL pubblico, tunnel o porte aperte.

Avvio: `scripts/install_bridge_service.sh` lo installa come LaunchAgent, che
lo riavvia dopo un crash e al login. `scripts/run_bridge.sh` lo lancia in
primo piano quando vuoi vedere il log scorrere.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# python-telegram-bot vive in un venv separato (.venv-bridge). L'import è
# protetto così i test possono importare gli helper puri senza installarlo.
try:
    from telegram import Update
    from telegram.constants import ChatAction
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
    _PTB_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
    _PTB_IMPORT_ERROR = exc

# --------------------------------------------------------------------------
# Costanti
# --------------------------------------------------------------------------

REPO_ROOT = Path(
    os.environ.get("BRIDGE_REPO_ROOT") or Path(__file__).resolve().parents[1]
)
SESSION_FILE = REPO_ROOT / ".claude_bridge_session"
PID_FILE = REPO_ROOT / ".claude_bridge.pid"
OUTBOX_DIR = REPO_ROOT / ".claude_bridge_outbox"

CLAUDE_TIMEOUT_S = 15 * 60
CHUNK_LIMIT = 3800          # cap Telegram 4096, margine per sicurezza
DOCUMENT_THRESHOLD = 10_000  # oltre questo: allegato .md, non un muro di chunk
TYPING_INTERVAL_S = 4

# Messaggi arrivati mentre il bridge era giù. NON vengono buttati — uno strumento
# che serve proprio quando sei lontano dalla macchina non può ingoiare in
# silenzio ciò che gli scrivi — ma oltre questa soglia non vengono nemmeno
# eseguiti a sorpresa: vengono elencati, e li rimandi tu se servono ancora.
STALE_MESSAGE_S = 15 * 60
MODEL = "sonnet"

TRANSCRIBE_TIMEOUT_S = 120
VOICE_MAX_BYTES = 20 * 1024 * 1024  # limite di download della Bot API locale

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

STARTED_AT = time.monotonic()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
logger = logging.getLogger("bridge")
logging.getLogger("httpx").setLevel(logging.WARNING)


class BridgeError(Exception):
    """Errore da mostrare all'utente. Porta con sé il session id se noto."""

    def __init__(self, message: str, session_id: str | None = None) -> None:
        super().__init__(message)
        self.session_id = session_id


# --------------------------------------------------------------------------
# Helper puri (coperti dai test — nessuna dipendenza da python-telegram-bot)
# --------------------------------------------------------------------------

def load_env(path: Path) -> dict[str, str]:
    """Parser .env minimale. Niente dotenv: una dipendenza in meno da installare."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def split_message(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Spezza `text` in blocchi <= limit, preferendo i confini di riga.

    Una riga più lunga di `limit` viene tagliata a forza: meglio un taglio
    brutto che un send fallito.
    """
    if not text:
        return []
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def load_session_id(path: Path = SESSION_FILE) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def save_session_id(session_id: str, path: Path = SESSION_FILE) -> None:
    path.write_text(session_id + "\n", encoding="utf-8")


def clear_session_id(path: Path = SESSION_FILE) -> bool:
    """True se un file di sessione esisteva ed è stato rimosso."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def claude_binary() -> str:
    """Percorso assoluto di `claude`.

    Sotto caffeinate/tmux/launchd il PATH può non contenere ~/.local/bin, quindi
    il fallback esplicito conta.
    """
    override = os.environ.get("CLAUDE_BIN")
    if override:
        return override
    found = shutil.which("claude")
    if found:
        return found
    return str(Path.home() / ".local" / "bin" / "claude")


def build_claude_argv(prompt: str, session_id: str | None) -> list[str]:
    argv = [
        claude_binary(),
        "-p", prompt,
        "--output-format", "json",
        "--model", MODEL,
        "--dangerously-skip-permissions",
    ]
    if session_id:
        argv += ["--resume", session_id]
    return argv


def parse_claude_result(stdout: str) -> tuple[str, str | None]:
    """Estrae (testo, session_id) dall'output JSON di `claude -p`.

    Solleva BridgeError su output non-JSON, `is_error`, o risultato vuoto —
    portandosi dietro il session_id quando c'è, così una sessione nata e poi
    fallita resta comunque riusabile: una sessione nuova ricarica da zero il
    contesto del repo (CLAUDE.md è grosso), il resume no.
    """
    stdout = stdout.strip()
    if not stdout:
        raise BridgeError("Claude Code non ha prodotto output.")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        raise BridgeError(
            "Output non-JSON da Claude Code:\n" + stdout[-800:]
        ) from None
    if not isinstance(payload, dict):
        raise BridgeError("Output JSON inatteso da Claude Code.")

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = None

    if payload.get("is_error"):
        detail = payload.get("result") or payload.get("subtype") or "errore sconosciuto"
        api_status = payload.get("api_error_status")
        suffix = f" (api_status={api_status})" if api_status else ""
        raise BridgeError(f"Claude Code ha risposto con errore{suffix}:\n{detail}", session_id)

    text = payload.get("result")
    if not isinstance(text, str) or not text.strip():
        raise BridgeError("Claude Code ha risposto senza testo.", session_id)
    return text, session_id


# --------------------------------------------------------------------------
# Trascrizione vocali (ffmpeg + whisper.cpp, tutto in locale)
# --------------------------------------------------------------------------

def ffmpeg_binary() -> str:
    override = os.environ.get("FFMPEG_BIN")
    if override:
        return override
    found = shutil.which("ffmpeg")
    if found:
        return found
    return "/opt/homebrew/bin/ffmpeg"


def whisper_cli_binary() -> str:
    override = os.environ.get("WHISPER_CLI_BIN")
    if override:
        return override
    found = shutil.which("whisper-cli")
    if found:
        return found
    return "/opt/homebrew/bin/whisper-cli"


def whisper_model_path() -> Path:
    override = os.environ.get("WHISPER_MODEL_PATH")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "models" / "ggml-large-v3-turbo.bin"


def build_ffmpeg_argv(src: Path, dst: Path) -> list[str]:
    """Converte in wav mono 16kHz: il formato che whisper.cpp sa decodificare
    in modo affidabile (l'ogg/opus dei vocali Telegram, testato, non va)."""
    return [
        ffmpeg_binary(), "-y", "-i", str(src),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(dst),
    ]


def build_whisper_argv(wav_path: Path, out_base: Path) -> list[str]:
    return [
        whisper_cli_binary(),
        "-m", str(whisper_model_path()),
        "-l", os.environ.get("WHISPER_LANGUAGE", "it"),
        "-nt", "-np",
        "-f", str(wav_path),
        "-otxt", "-of", str(out_base),
    ]


async def _run_subprocess(argv: list[str], timeout: float) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass
        raise BridgeError(f"Timeout dopo {int(timeout)}s durante la trascrizione.") from None
    return (
        process.returncode,
        stdout_b.decode("utf-8", "replace"),
        stderr_b.decode("utf-8", "replace"),
    )


async def transcribe_voice(src_path: Path) -> str:
    """Converte `src_path` (vocale Telegram, ogg/opus) e lo trascrive in locale.

    Solleva BridgeError con un messaggio azionabile — mai un errore muto — se
    manca un binario, il modello, o conversione/trascrizione falliscono.
    """
    model_path = whisper_model_path()
    if not model_path.exists():
        raise BridgeError(
            f"Modello whisper mancante: {model_path}\n"
            "Scaricane uno da https://huggingface.co/ggerganov/whisper.cpp/tree/main "
            "(es. ggml-large-v3-turbo.bin) o imposta WHISPER_MODEL_PATH nel .env."
        )
    ffmpeg_path = ffmpeg_binary()
    if not Path(ffmpeg_path).exists():
        raise BridgeError(f"ffmpeg non trovato ({ffmpeg_path}) — installa con `brew install ffmpeg`.")
    whisper_path = whisper_cli_binary()
    if not Path(whisper_path).exists():
        raise BridgeError(f"whisper-cli non trovato ({whisper_path}) — installa con `brew install whisper-cpp`.")

    with tempfile.TemporaryDirectory(prefix="bridge-voice-") as tmpdir:
        tmp = Path(tmpdir)
        wav_path = tmp / "audio.wav"
        out_base = tmp / "transcript"

        returncode, _, stderr = await _run_subprocess(
            build_ffmpeg_argv(src_path, wav_path), timeout=TRANSCRIBE_TIMEOUT_S
        )
        if returncode != 0 or not wav_path.exists():
            raise BridgeError("Conversione audio fallita:\n" + (stderr[-500:] or "(nessun stderr)"))

        returncode, _, stderr = await _run_subprocess(
            build_whisper_argv(wav_path, out_base), timeout=TRANSCRIBE_TIMEOUT_S
        )
        out_txt = out_base.with_suffix(".txt")
        if returncode != 0 or not out_txt.exists():
            raise BridgeError("Trascrizione fallita:\n" + (stderr[-500:] or "(nessun stderr)"))

        text = out_txt.read_text(encoding="utf-8").strip()
        if not text:
            raise BridgeError("Trascrizione vuota — audio silenzioso o non udibile.")
        return text


def message_age_s(message_date: "datetime | None") -> float | None:
    """Età in secondi di un messaggio Telegram, o None se la data manca."""
    if message_date is None:
        return None
    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - message_date).total_seconds()


def is_stale(message_date: "datetime | None", limit_s: float = STALE_MESSAGE_S) -> bool:
    age = message_age_s(message_date)
    return age is not None and age > limit_s


def format_uptime(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def git_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


# --------------------------------------------------------------------------
# Istanza singola: Telegram accetta un solo getUpdates per token (409 Conflict)
# --------------------------------------------------------------------------

def acquire_single_instance_lock(path: Path = PID_FILE) -> None:
    if path.exists():
        try:
            other = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            other = None
        if other and other != os.getpid():
            try:
                os.kill(other, 0)
            except OSError:
                pass  # PID morto: lock stantio, lo sovrascriviamo
            else:
                sys.exit(
                    f"Un altro bridge è già in esecuzione (pid {other}). "
                    "Telegram accetta un solo getUpdates per token."
                )
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def release_single_instance_lock(path: Path = PID_FILE) -> None:
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass


# --------------------------------------------------------------------------
# Stato runtime
# --------------------------------------------------------------------------

class BridgeState:
    def __init__(self, allowed_chat_id: int) -> None:
        self.allowed_chat_id = allowed_chat_id
        self.lock = asyncio.Lock()
        self.process: "asyncio.subprocess.Process | None" = None
        self.cancelled = False


STATE: BridgeState | None = None


def _authorized(update: "Update") -> bool:
    """Primo controllo di ogni handler. Chat non in allowlist → False, e silenzio."""
    assert STATE is not None
    chat = update.effective_chat
    chat_id = chat.id if chat else None
    if chat_id != STATE.allowed_chat_id:
        user = update.effective_user
        logger.warning(
            "Accesso rifiutato: chat_id=%s user_id=%s username=%s",
            chat_id,
            user.id if user else None,
            user.username if user else None,
        )
        return False
    return True


# --------------------------------------------------------------------------
# Esecuzione di Claude Code
# --------------------------------------------------------------------------

async def _typing_loop(bot, chat_id: int) -> None:
    try:
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception as exc:  # rete ballerina: non deve uccidere il comando
                logger.debug("send_chat_action fallita: %s", exc)
            await asyncio.sleep(TYPING_INTERVAL_S)
    except asyncio.CancelledError:
        pass


def _kill_process_group(process: "asyncio.subprocess.Process") -> None:
    """Uccide l'intero gruppo: claude genera figli (subagent, tool bash)."""
    if process.returncode is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass


async def run_claude(prompt: str) -> tuple[str, str | None]:
    """Esegue `claude -p` nel repo. Ritorna (testo, session_id).

    Se la sessione salvata non esiste più (cancellata, scaduta, repo spostato)
    `--resume` fallisce. Senza recupero il bridge risponderebbe lo stesso errore
    a ogni messaggio, per sempre: da Kalymnos sarebbe irrecuperabile. Quindi al
    primo fallimento di resume la sessione viene buttata e il comando ritentato
    da zero, una volta sola.
    """
    try:
        return await _run_claude_once(prompt, load_session_id())
    except BridgeError as exc:
        if not load_session_id() or not _is_stale_session_error(str(exc)):
            raise
        logger.warning("Sessione salvata non più valida — riparto da zero.")
        clear_session_id()
        return await _run_claude_once(prompt, None)


def _is_stale_session_error(message: str) -> bool:
    lowered = message.lower()
    return "--resume" in lowered or "no conversation found" in lowered


async def _run_claude_once(prompt: str, session_id: str | None) -> tuple[str, str | None]:
    assert STATE is not None
    argv = build_claude_argv(prompt, session_id)
    logger.info(
        "Eseguo claude (%s sessione, cwd=%s)",
        "resume" if session_id else "nuova", REPO_ROOT,
    )

    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        start_new_session=True,  # gruppo di processi proprio → killpg pulito
    )
    STATE.process = process
    STATE.cancelled = False
    try:
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                process.communicate(), timeout=CLAUDE_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            _kill_process_group(process)
            raise BridgeError(
                f"Timeout dopo {CLAUDE_TIMEOUT_S // 60} minuti — processo ucciso. "
                "La sessione resta valida: riprova con un comando più stretto."
            ) from None
    finally:
        STATE.process = None

    if STATE.cancelled:
        raise BridgeError("Comando interrotto con /stop.")

    stderr = stderr_b.decode("utf-8", "replace").strip()
    if process.returncode != 0 and not stdout_b.strip():
        raise BridgeError(
            f"claude è uscito con codice {process.returncode}.\n"
            + (stderr[-800:] or "(nessun stderr)")
        )
    if stderr:
        logger.warning("stderr da claude: %s", stderr[-500:])

    return parse_claude_result(stdout_b.decode("utf-8", "replace"))


async def deliver(update: "Update", text: str) -> None:
    """Manda `text` in chat. Niente parse_mode: backtick/asterischi/underscore
    dell'output di Claude romperebbero il parser Markdown di Telegram, con send
    che falliscono in silenzio. Plain text è la scelta robusta."""
    chat = update.effective_chat
    assert chat is not None

    if len(text) > DOCUMENT_THRESHOLD:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", prefix="claude-", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(text)
            temp_path = Path(handle.name)
        try:
            with temp_path.open("rb") as fh:
                await chat.send_document(
                    document=fh,
                    filename="risposta.md",
                    caption=f"Risposta lunga ({len(text)} caratteri) — allegata.",
                )
        finally:
            temp_path.unlink(missing_ok=True)
        return

    for chunk in split_message(text):
        await chat.send_message(chunk)


async def _flush_outbox(send_photo, send_document) -> None:
    """Nucleo condiviso: manda ed elimina ogni file lasciato in OUTBOX_DIR.

    `send_photo(fh, caption)` / `send_document(fh, filename)` astraggono la
    differenza fra `Chat.send_photo` (dentro un turno, la chat è già nota) e
    `Bot.send_photo` (all'avvio, serve `chat_id` esplicito — vedi
    `_startup_flush_outbox`). Sempre svuotata, invio riuscito o no, per non
    far accumulare file di un tentativo fallito a metà.
    """
    if not OUTBOX_DIR.is_dir():
        return
    for path in sorted(p for p in OUTBOX_DIR.iterdir() if p.is_file()):
        try:
            with path.open("rb") as fh:
                if path.suffix.lower() in IMAGE_EXTENSIONS:
                    await send_photo(fh, path.stem)
                else:
                    await send_document(fh, path.name)
        except Exception:
            logger.exception("Invio outbox fallito per %s", path)
        finally:
            path.unlink(missing_ok=True)


async def deliver_outbox(update: "Update") -> None:
    """Manda ed elimina ogni file lasciato in OUTBOX_DIR durante il turno.

    `claude -p --output-format json` restituisce solo testo — non c'è altro
    canale per un turno che produce un'immagine (es. uno schizzo di topo, A278)
    di dirlo al bridge. Convenzione: scrivi il file in OUTBOX_DIR, il bridge lo
    trova qui a fine turno e lo allega. Immagini → foto, tutto il resto →
    documento.
    """
    chat = update.effective_chat
    assert chat is not None
    await _flush_outbox(
        send_photo=lambda fh, caption: chat.send_photo(photo=fh, caption=caption),
        send_document=lambda fh, filename: chat.send_document(document=fh, filename=filename),
    )


async def _startup_flush_outbox(application: "Application") -> None:
    """`post_init` del bridge: consegna un'outbox rimasta piena da un avvio
    precedente appena il bot è pronto, senza aspettare un nuovo messaggio.

    Il bridge non si riavvia mai da solo a metà di un turno (`_execute_and_deliver`
    lo aspetta), ma un riavvio manuale — o uno che arriva mentre il turno
    successivo non è ancora partito — lascerebbe l'outbox piena fino al primo
    messaggio in arrivo. Da qui parte subito, con `STATE.allowed_chat_id`
    invece della chat di un update.
    """
    assert STATE is not None
    if not OUTBOX_DIR.is_dir() or not any(OUTBOX_DIR.iterdir()):
        return
    logger.info("Outbox non vuota all'avvio — la consegno prima di aprire il polling.")
    bot = application.bot
    chat_id = STATE.allowed_chat_id
    await _flush_outbox(
        send_photo=lambda fh, caption: bot.send_photo(chat_id=chat_id, photo=fh, caption=caption),
        send_document=lambda fh, filename: bot.send_document(chat_id=chat_id, document=fh, filename=filename),
    )


# --------------------------------------------------------------------------
# Handler
# --------------------------------------------------------------------------

async def _execute_and_deliver(update: "Update", context: "ContextTypes.DEFAULT_TYPE", prompt: str) -> None:
    """Esegue `prompt` con Claude Code e manda la risposta in chat.

    Va chiamata con STATE.lock già acquisito dal chiamante — è condivisa fra
    on_message e on_voice, che differiscono solo in come ottengono `prompt`.
    """
    assert STATE is not None
    try:
        typing = asyncio.create_task(_typing_loop(context.bot, update.effective_chat.id))
        try:
            text, session_id = await run_claude(prompt)
        except BridgeError as exc:
            if exc.session_id:
                save_session_id(exc.session_id)
            logger.error("Comando fallito: %s", exc)
            await deliver(update, f"⚠️ {exc}")
            return
        except Exception as exc:  # il bridge non deve morire per un comando
            logger.exception("Errore inatteso")
            await deliver(update, f"⚠️ Errore inatteso nel bridge: {exc!r}")
            return
        finally:
            typing.cancel()

        if session_id:
            save_session_id(session_id)
        await deliver(update, text)
    finally:
        await deliver_outbox(update)


async def _skip_if_stale(message, preview: str) -> bool:
    """True se il messaggio è troppo vecchio per essere eseguito adesso.

    Il bridge non butta più la coda al riavvio, quindi ciò che hai scritto mentre
    il Mac era giù arriva comunque — ma eseguirlo a ore di distanza, senza che tu
    stia guardando, è peggio che non eseguirlo. Qui te lo diciamo e ci fermiamo.
    """
    if not is_stale(message.date):
        return False
    minutes = int((message_age_s(message.date) or 0) // 60)
    short = preview if len(preview) <= 120 else preview[:117] + "…"
    logger.warning("Messaggio stantio ignorato (%s min): %s", minutes, short)
    await message.reply_text(
        f"Questo messaggio ha {minutes} minuti — il bridge era giù quando l'hai "
        f"mandato, quindi non lo eseguo a sorpresa.\n\n«{short}»\n\n"
        "Rimandalo se serve ancora."
    )
    return True


async def on_message(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
    if not _authorized(update):
        return
    assert STATE is not None
    message = update.effective_message
    if message is None or not (message.text or "").strip():
        return
    prompt = message.text.strip()

    if await _skip_if_stale(message, prompt):
        return

    if STATE.lock.locked():
        await message.reply_text("Occupato — un comando è già in esecuzione. /stop per annullarlo.")
        return

    async with STATE.lock:
        await _execute_and_deliver(update, context, prompt)


async def on_voice(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
    if not _authorized(update):
        return
    assert STATE is not None
    message = update.effective_message
    if message is None:
        return
    voice = message.voice or message.audio
    if voice is None:
        return

    if await _skip_if_stale(message, "(vocale)"):
        return

    if STATE.lock.locked():
        await message.reply_text("Occupato — un comando è già in esecuzione. /stop per annullarlo.")
        return

    if voice.file_size and voice.file_size > VOICE_MAX_BYTES:
        await message.reply_text(
            f"Audio troppo grande ({voice.file_size // 1024} KB, "
            f"max {VOICE_MAX_BYTES // (1024 * 1024)} MB)."
        )
        return

    async with STATE.lock:
        try:
            tg_file = await voice.get_file()
            with tempfile.TemporaryDirectory(prefix="bridge-voice-src-") as tmpdir:
                src_path = Path(tmpdir) / "voice.ogg"
                await tg_file.download_to_drive(custom_path=str(src_path))
                prompt = await transcribe_voice(src_path)
        except BridgeError as exc:
            logger.error("Trascrizione fallita: %s", exc)
            await deliver(update, f"⚠️ {exc}")
            return
        except Exception as exc:
            logger.exception("Errore inatteso nella trascrizione")
            await deliver(update, f"⚠️ Errore inatteso nella trascrizione: {exc!r}")
            return

        await message.reply_text(f"🎙️ trascritto: {prompt}")
        await _execute_and_deliver(update, context, prompt)


async def cmd_new(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
    if not _authorized(update):
        return
    had = clear_session_id()
    await update.effective_message.reply_text(
        "Sessione azzerata — il prossimo messaggio ne apre una nuova.\n"
        "Nota: un boot a freddo rilegge tutto CLAUDE.md senza cache (è grosso), "
        "quindi è più lento del resume — ma sei su abbonamento Max: nessun costo "
        "a consumo, incluso nel piano."
        if had else
        "Nessuna sessione salvata: il prossimo messaggio ne apre già una nuova."
    )


async def cmd_status(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
    if not _authorized(update):
        return
    assert STATE is not None
    session_id = load_session_id()
    lines = [
        f"sessione : {session_id[:8] + '…' if session_id else '(nessuna, prossimo messaggio = nuova)'}",
        f"uptime   : {format_uptime(time.monotonic() - STARTED_AT)}",
        f"cwd      : {REPO_ROOT}",
        f"branch   : {git_branch()}",
        f"in corso : {'sì' if STATE.lock.locked() else 'no'}",
    ]
    await update.effective_message.reply_text("\n".join(lines))


async def cmd_stop(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
    if not _authorized(update):
        return
    assert STATE is not None
    process = STATE.process
    if process is None:
        await update.effective_message.reply_text("Niente da fermare.")
        return
    STATE.cancelled = True
    _kill_process_group(process)
    await update.effective_message.reply_text("Processo ucciso.")


async def cmd_help(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
    if not _authorized(update):
        return
    await update.effective_message.reply_text(
        "Scrivimi un messaggio (testo o vocale) e lo eseguo con Claude Code in "
        f"{REPO_ROOT.name}.\n\n"
        "I vocali vengono trascritti in locale (whisper.cpp) prima dell'esecuzione.\n\n"
        "/new    — azzera la sessione, il prossimo messaggio ne apre una nuova\n"
        "/status — sessione, uptime, cwd, branch, comando in corso\n"
        "/stop   — uccide il comando in esecuzione\n"
        "/help   — questo messaggio\n\n"
        f"Un comando alla volta. Timeout {CLAUDE_TIMEOUT_S // 60} minuti.\n"
        "Il bridge non fa mai `git push` da solo: chiedilo e lo fa Claude Code."
    )


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> None:
    global STATE

    if _PTB_IMPORT_ERROR is not None:
        sys.exit(
            f"python-telegram-bot non installato ({_PTB_IMPORT_ERROR}).\n"
            "  python3 -m venv .venv-bridge\n"
            "  .venv-bridge/bin/pip install -r scripts/requirements-bridge.txt"
        )

    env = {**load_env(REPO_ROOT / ".env"), **os.environ}
    token = env.get("TELEGRAM_BRIDGE_TOKEN")
    raw_chat_id = env.get("TELEGRAM_ALLOWED_CHAT_ID")
    if not token:
        sys.exit("TELEGRAM_BRIDGE_TOKEN mancante in .env — vedi header di questo file.")
    if not raw_chat_id:
        sys.exit("TELEGRAM_ALLOWED_CHAT_ID mancante in .env — vedi header di questo file.")
    try:
        allowed_chat_id = int(raw_chat_id)
    except ValueError:
        sys.exit(f"TELEGRAM_ALLOWED_CHAT_ID non è un intero: {raw_chat_id!r}")

    acquire_single_instance_lock()
    STATE = BridgeState(allowed_chat_id)

    application = Application.builder().token(token).post_init(_startup_flush_outbox).build()
    application.add_handler(CommandHandler("new", cmd_new))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler(["help", "start"], cmd_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))

    logger.info("Bridge avviato — repo=%s chat autorizzata=%s", REPO_ROOT, allowed_chat_id)
    try:
        # drop_pending_updates=False di proposito: buttare la coda al riavvio
        # significa perdere in silenzio i messaggi mandati mentre il Mac era giù,
        # che è esattamente quando questo strumento serve. Li riceviamo tutti; a
        # non eseguire quelli vecchi ci pensa _skip_if_stale, che almeno lo dice.
        application.run_polling(drop_pending_updates=False)
    finally:
        release_single_instance_lock()
        logger.info("Bridge fermato.")


if __name__ == "__main__":
    main()
