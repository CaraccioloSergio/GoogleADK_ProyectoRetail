from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types  # Content, Part

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# --- Paths base ---
BASE_DIR = Path(__file__).resolve().parent          # ...\retail-agent-demo
RETAIL_AGENT_DIR = BASE_DIR / "retail_agent"        # ...\retail-agent-demo\retail_agent

# --- Cargar .env de retail_agent ---
ENV_PATH = RETAIL_AGENT_DIR / ".env"
load_dotenv(ENV_PATH)

# (opcional: debug sin mostrar la clave)
print("DEBUG GOOGLE_API_KEY presente?:", bool(os.getenv("GOOGLE_API_KEY")))

# --- Hacer que Python vea retail_agent como módulo ---
sys.path.insert(0, str(RETAIL_AGENT_DIR))

from agent import root_agent  # Milo, el agente que pegaste recién

APP_NAME = "retail_whatsapp"

# -------------------------
# ADK: Runner + sesiones
# -------------------------
session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

app = FastAPI(title="Retail WhatsApp Bridge")


async def ensure_session(user_id: str) -> str:
    """
    Garantiza que exista una sesión para este user_id.
    Devuelve el session_id a usar.
    """
    session_id = user_id

    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    return session.id


async def run_whatsapp_turn(user_id: str, body: str) -> str:
    """
    Ejecuta un turno del agente ADK para un número de WhatsApp.

    user_id: número de WhatsApp (por ejemplo: +5491160149350).
    """
    session_id = await ensure_session(user_id)

    # Enriquecemos el mensaje para que Milo sepa el número de WhatsApp
    enriched_text = (
        "Contexto para vos, Milo: el usuario te está escribiendo desde WhatsApp.\n"
        f"Su número de WhatsApp es: {user_id}.\n"
        "Usá este número como `phone` cuando llames a `search_users` o `create_user`.\n"
        "No le pidas el teléfono a menos que el usuario diga que quiere actualizarlo.\n\n"
        f"Mensaje del usuario:\n{body}"
    )

    content = types.Content(
        role="user",
        parts=[types.Part(text=enriched_text)],
    )

    final_text = (
        "Perdón, hubo un problema procesando tu mensaje. "
        "Probá de nuevo en un toque."
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            part = event.content.parts[0]
            if getattr(part, "text", None):
                final_text = part.text

    return final_text


# -------------------------
# Endpoint para Twilio WhatsApp
# -------------------------
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook que Twilio llama cuando llega un WhatsApp.
    Responde con TwiML (XML) para que Twilio envíe el mensaje.
    """
    form = await request.form()
    print("🔔 Twilio form:", dict(form))  # 👈 para debug

    body = (form.get("Body") or "").strip()
    wa_id = form.get("WaId") or ""
    from_number = wa_id or (form.get("From") or "")

    if not body:
        reply_text = "No recibí ningún texto en tu mensaje 🙂"
    else:
        reply_text = await run_whatsapp_turn(from_number, body)

    twiml = MessagingResponse()
    twiml.message(reply_text)

    # Twilio espera XML (TwiML)
    return Response(content=str(twiml), media_type="application/xml")
