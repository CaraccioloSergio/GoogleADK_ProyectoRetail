from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, FileResponse
from twilio.twiml.messaging_response import MessagingResponse

# Validación Twilio (opcional)
from twilio.request_validator import RequestValidator

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
import uuid
import time
import asyncio

import httpx
from dotenv import load_dotenv


# ============================================================
# FFmpeg (Whisper dependency) - ensure python can see ffmpeg
# ============================================================
FFMPEG_DIR = os.getenv("FFMPEG_DIR", r"C:\ffmpeg\bin")

if shutil.which("ffmpeg") is None:
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
    print(f"🔧 PATH patched with FFMPEG_DIR={FFMPEG_DIR}")

print(f"🎛️ ffmpeg visible to python: {shutil.which('ffmpeg')}")


# ============================================================
# Paths / env
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
RETAIL_AGENT_DIR = BASE_DIR / "retail_agent"
ENV_PATH = RETAIL_AGENT_DIR / ".env"

# Solo cargar .env en local/dev
if (os.getenv("ENV", "") or "").lower() in ("dev", "local", ""):
    load_dotenv(ENV_PATH, override=False)

# --- ADK import ---
sys.path.insert(0, str(RETAIL_AGENT_DIR))
from agent import root_agent  # noqa


APP_NAME = "retail_whatsapp"

# -------------------------
# ADK: Runner + sesiones
# -------------------------
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

app = FastAPI(title="Retail WhatsApp Bridge")

# -------------------------
# Twilio validation (toggle)
# -------------------------
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_VALIDATE = (os.getenv("TWILIO_VALIDATE", "false") or "").lower() == "true"
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "+12293184978")  # 🔹 NUEVA LÍNEA

twilio_validator = (
    RequestValidator(TWILIO_AUTH_TOKEN)
    if (TWILIO_VALIDATE and TWILIO_AUTH_TOKEN)
    else None
)

# -------------------------
# STT config
# -------------------------
STT_PROVIDER = (os.getenv("STT_PROVIDER", "whisper_local") or "").lower()  # whisper_local | none
STT_LANGUAGE = (os.getenv("STT_LANGUAGE", "es") or "").strip() or None
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny | base | small | medium | large

# -------------------------
# TTS config (voice replies)
# -------------------------
VOICE_REPLY_MODE = (os.getenv("VOICE_REPLY_MODE", "off") or "").lower()  # off | always | mirror
TTS_PROVIDER = (os.getenv("TTS_PROVIDER", "gcp") or "").lower()          # gcp | none
TTS_LANGUAGE_CODE = os.getenv("TTS_LANGUAGE_CODE", "es-AR")
TTS_VOICE_NAME = os.getenv("TTS_VOICE_NAME", "es-AR-Standard-A")
TTS_AUDIO_ENCODING = (os.getenv("TTS_AUDIO_ENCODING", "MP3") or "").upper()  # MP3 | OGG_OPUS
MEDIA_TTL_SECONDS = int(os.getenv("MEDIA_TTL_SECONDS", "600"))
VOICE_AUDIO_FALLBACK_TO_TEXT = (os.getenv("VOICE_AUDIO_FALLBACK_TO_TEXT", "true") or "").lower() == "true"



# ============================================================
# Helpers
# ============================================================
def _public_url_from_request(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    path = request.url.path
    return f"{proto}://{host}{path}"

def get_public_base_url(request: Request) -> str:
    """
    Devuelve la base pública para construir URLs accesibles por Twilio.
    Prioriza PUBLIC_BASE_URL (ngrok), sino intenta con headers.
    """
    env_base = (os.getenv("PUBLIC_BASE_URL", "") or "").strip()
    if env_base:
        return env_base.rstrip("/")

    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{proto}://{host}"

def validate_twilio_request(request: Request, form_data: dict):
    if not twilio_validator:
        return  # desactivado

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(status_code=403, detail="Forbidden")

    url = _public_url_from_request(request)
    ok = twilio_validator.validate(url, form_data, signature)
    if not ok:
        raise HTTPException(status_code=403, detail="Forbidden")


async def ensure_session(user_id: str) -> str:
    """Asegura que existe una sesión para el usuario"""
    session_id = user_id
    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            session = await session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        return session.id
    except Exception as e:
        print(f"❌ Error creando sesión: {e}")
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        return session.id


async def run_whatsapp_turn(user_id: str, body: str) -> str:
    """Ejecuta un turno de conversación con el agente"""
    try:
        session_id = await ensure_session(user_id)

        enriched_text = (
            f"[INFO INTERNA: Usuario WhatsApp #{user_id}]\n\n"
            f"{body}"
        )

        content = types.Content(role="user", parts=[types.Part(text=enriched_text)])

        final_text = "Perdón, tuve un problema procesando tu mensaje. Probá de nuevo en un toque."

        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            # Debug tools (opcional)
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    func_call = getattr(part, "function_call", None)
                    if func_call and hasattr(func_call, "name"):
                        print(f"🔧 Tool call: {func_call.name}")

                    func_resp = getattr(part, "function_response", None)
                    if func_resp and hasattr(func_resp, "name"):
                        response_data = getattr(func_resp, "response", {})
                        print(f"✅ Tool response: {func_resp.name}")
                        print(f"📊 Response data: {response_data}")

            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        txt = getattr(part, "text", None)
                        if txt:
                            final_text = txt
                            break
                if final_text != "Perdón, tuve un problema procesando tu mensaje. Probá de nuevo en un toque.":
                    break

        return final_text

    except Exception as e:
        print(f"❌ Error en run_whatsapp_turn: {e}")
        import traceback
        traceback.print_exc()
        return "Perdón, hubo un problema técnico. Probá de nuevo en un ratito."


# ============================================================
# Media + STT
# ============================================================
def _is_audio_content_type(content_type: str) -> bool:
    ct = (content_type or "").lower().strip()
    return ct.startswith("audio/") or ct in ("application/ogg",)


def _ffmpeg_to_wav_16k_mono(input_path: str) -> str:
    """Convierte el audio a WAV mono 16k (mejora STT con WhatsApp/OPUS)."""
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    out_path = out.name
    out.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ac", "1",        # mono
        "-ar", "16000",    # 16k
        out_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path


async def _download_twilio_media(media_url: str, content_type: str) -> str:
    """
    Descarga el media desde Twilio y lo guarda en un archivo temporal.
    Retorna el path local.
    """
    if not media_url:
        raise ValueError("media_url vacío")

    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        raise RuntimeError("Faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN para descargar media")

    # Extensión según content-type
    ext = ".bin"
    ct = (content_type or "").lower()
    if "ogg" in ct:
        ext = ".ogg"
    elif "mpeg" in ct or "mp3" in ct:
        ext = ".mp3"
    elif "wav" in ct:
        ext = ".wav"
    elif "mp4" in ct or "m4a" in ct:
        ext = ".m4a"
    elif "webm" in ct:
        ext = ".webm"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp_path = tmp.name
    tmp.close()

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(r.content)

    return tmp_path


def _transcribe_whisper_local(audio_path: str) -> str:
    """STT con Whisper local (requiere ffmpeg)."""
    import whisper  # pip install openai-whisper

    model = whisper.load_model(WHISPER_MODEL)

    kwargs = {"task": "transcribe"}
    if STT_LANGUAGE:
        kwargs["language"] = STT_LANGUAGE

    # Prompt guía (mejora español + contexto supermercado)
    kwargs["initial_prompt"] = (
        "Español rioplatense. Conversación informal por WhatsApp. "
        "Transcribí fielmente lo que se dice, sin inventar palabras."
    )

    result = model.transcribe(audio_path, **kwargs)
    return (result.get("text") or "").strip()


def _transcribe_gemini(audio_path: str) -> str:
    """STT con Gemini (multimodal)."""
    from google import genai
    from google.genai import types
    
    # Leer audio como bytes
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    
    # Crear cliente
    client = genai.Client()
    
    # Determinar mime type según extensión
    ext = audio_path.lower()
    if ext.endswith('.ogg'):
        mime_type = "audio/ogg"
    elif ext.endswith('.mp3'):
        mime_type = "audio/mpeg"
    elif ext.endswith('.wav'):
        mime_type = "audio/wav"
    elif ext.endswith('.m4a'):
        mime_type = "audio/mp4"
    else:
        mime_type = "audio/mpeg"  # fallback
    
    # Prompt para transcripción
    prompt = (
        "Transcribí este audio en español rioplatense. "
        "Solo devolvé el texto exacto de lo que se dice, sin agregar nada más."
    )
    
    # Generar con audio usando el mismo modelo del agente
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            prompt
        ]
    )
    
    return (response.text or "").strip()


def transcribe_audio(audio_path: str) -> str:
    provider = STT_PROVIDER
    if provider in ("none", "off", "false"):
        return ""
    if provider == "whisper_local":
        return _transcribe_whisper_local(audio_path)
    if provider == "gemini":
        return _transcribe_gemini(audio_path)
    raise RuntimeError(f"STT_PROVIDER no soportado: {provider}")

def tts_to_audio_file(text: str) -> str:
    """
    Genera un archivo de audio (mp3 u ogg opus) desde un texto usando Google Cloud TTS.
    Devuelve el path del archivo.
    """
    if TTS_PROVIDER in ("none", "off", "false"):
        return ""

    if TTS_PROVIDER != "gcp":
        raise RuntimeError(f"TTS_PROVIDER no soportado: {TTS_PROVIDER}")

    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Voz
    voice = texttospeech.VoiceSelectionParams(
        language_code=TTS_LANGUAGE_CODE,
        name=TTS_VOICE_NAME,
    )

    # Encoding
    if TTS_AUDIO_ENCODING == "OGG_OPUS":
        audio_encoding = texttospeech.AudioEncoding.OGG_OPUS
        suffix = ".ogg"
        mime = "audio/ogg"
    else:
        audio_encoding = texttospeech.AudioEncoding.MP3
        suffix = ".mp3"
        mime = "audio/mpeg"

    audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding)

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    tmp.close()

    with open(tmp_path, "wb") as out:
        out.write(response.audio_content)

    # Guardamos MIME para servirlo correcto (lo retornamos como tuple encubierto)
    # Para mantenerlo simple, devolvemos solo path y usamos encoding para mime en el endpoint.
    return tmp_path

# ============================================================
# In-memory media store for TTS replies (simple TTL)
# ============================================================
MEDIA_STORE = {}  # media_id -> {"path": str, "expires": float}

# ============================================================
# Startup warmup (backoffice)
# ============================================================
@app.on_event("startup")
async def warmup_backoffice():
    """
    Al iniciar el servidor, hace una request al backoffice
    para 'calentarlo' y evitar cold starts en las primeras interacciones.
    """
    import asyncio

    backoffice_url = os.getenv("BACKOFFICE_BASE_URL", "")
    if not backoffice_url or "localhost" in backoffice_url or "127.0.0.1" in backoffice_url:
        print("⚡ Modo local, skip warmup")
        return

    async def warmup():
        try:
            print(f"🔥 Calentando backoffice: {backoffice_url}")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{backoffice_url}/products",
                    headers={"x-api-key": os.getenv("BACKOFFICE_API_KEY", "")}
                )
                if resp.status_code == 200:
                    print("✅ Backoffice calentado exitosamente")
                else:
                    print(f"⚠️  Backoffice respondió con {resp.status_code}")
        except Exception as e:
            print(f"⚠️  Error calentando backoffice: {e}")

    asyncio.create_task(warmup())


# ============================================================
# WORKER REAL (función sin decorator @app.post)
# ============================================================
async def process_message_worker(payload: dict):
    """
    Worker real: STT + agente + envío de respuesta.
    Se ejecuta en background sin bloquear el webhook.
    """
    try:
        body = payload.get("Body", "")
        wa_id = payload.get("WaId", "")
        from_raw = payload.get("From", "")
        num_media = payload.get("NumMedia", 0)
        media_url = payload.get("MediaUrl0", "")
        media_ct = payload.get("MediaContentType0", "")

        user_id = wa_id or from_raw.replace("whatsapp:", "").replace("+", "") or "unknown"

        print(f"🔄 Procesando mensaje de user_id={user_id}")

        effective_text = body

        # --- AUDIO IN ---
        if num_media > 0 and _is_audio_content_type(media_ct):
            print("🎧 Procesando audio en worker")
            audio_path = None
            wav_path = None
            try:
                audio_path = await _download_twilio_media(media_url, media_ct)
                wav_path = _ffmpeg_to_wav_16k_mono(audio_path)
                transcript = transcribe_audio(wav_path)
                effective_text = transcript or ""
                print(f"📝 Transcripción: {effective_text}")
            except Exception as e:
                print(f"❌ Error en STT: {e}")
                import traceback
                traceback.print_exc()
                effective_text = ""
            finally:
                if wav_path:
                    try: os.remove(wav_path)
                    except: pass
                if audio_path:
                    try: os.remove(audio_path)
                    except: pass

        if not effective_text:
            reply_text = "No pude entender el mensaje 😕"
        else:
            print(f"🤖 Enviando a agente: {effective_text[:50]}...")
            reply_text = await run_whatsapp_turn(user_id, effective_text)
            print(f"💬 Respuesta del agente: {reply_text[:50]}...")

        # --- RESPUESTA POR TWILIO REST ---
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",  # usa variable de entorno
            to=from_raw,
            body=reply_text
        )

        print(f"✅ Mensaje enviado. SID: {message.sid}")

    except Exception as e:
        print(f"❌ Error en worker: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# Routes
# ============================================================
@app.get("/")
async def health_check():
    return {"status": "ok", "service": "whatsapp_server"}

@app.get("/media/{media_id}")
async def get_media(media_id: str):
    print(f"📡 Twilio pidió /media/{media_id}")
    item = MEDIA_STORE.get(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")

    if time.time() > item["expires"]:
        # expirado
        try:
            os.remove(item["path"])
        except Exception:
            pass
        MEDIA_STORE.pop(media_id, None)
        raise HTTPException(status_code=404, detail="Expired")

    path = item["path"]
    # Mime según extensión
    if path.lower().endswith(".ogg"):
        media_type = "audio/ogg"
        filename = "reply.ogg"
    else:
        media_type = "audio/mpeg"
        filename = "reply.mp3"

    return FileResponse(path, media_type=media_type, filename=filename)


@app.post("/whatsapp")
@app.post("/whatsapp/")
async def whatsapp_webhook(request: Request):
    """
    Webhook rápido: valida, encola y responde OK.
    """
    try:
        form = await request.form()

        payload = {
            "Body": (form.get("Body") or "").strip(),
            "WaId": (form.get("WaId") or "").strip(),
            "From": (form.get("From") or "").strip(),
            "NumMedia": int(form.get("NumMedia") or 0),
            "MediaUrl0": (form.get("MediaUrl0") or "").strip(),
            "MediaContentType0": (form.get("MediaContentType0") or "").strip(),
        }

        print(f"📥 Webhook recibido de {payload['From']}")
        print(f"📝 Body: {payload['Body']}")

        # 🔹 Encolamos el worker en background
        asyncio.create_task(process_message_worker(payload))

        # RESPUESTA INMEDIATA A TWILIO (TwiML vacío pero válido)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 
            media_type="application/xml", 
            status_code=200
        )

    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 
            media_type="application/xml", 
            status_code=200
        )


@app.post("/")
async def whatsapp_webhook_root(request: Request):
    """Alias del webhook en raíz para compatibilidad"""
    return await whatsapp_webhook(request)