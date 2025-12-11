# retail_agent/runtime_whatsapp.py

from google.adk import types  # type: ignore
from google.adk.runtime import Runner  # type: ignore
from google.adk.sessions import InMemorySessionService  # type: ignore

from agent import root_agent


APP_NAME = "retail_assistant"

# ============================
# Servicios compartidos
# ============================
session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


# ============================
# Función que usa el webhook
# ============================
async def run_whatsapp_turn(user_id: str, message_text: str) -> str:
    """
    Ejecuta un turno de conversación para un usuario de WhatsApp.

    - user_id: normalmente el número que viene en From (ej. 'whatsapp:+54911...').
    - message_text: texto que escribió la persona.
    """

    # Construimos el contenido con el mensaje del usuario.
    content = types.Content(
        role="user",
        parts=[types.Part(text=message_text)],
    )

    # DEBUG: logueamos qué entra
    print(f"[ADK] Mensaje de {user_id}: {message_text}", flush=True)

    # 1) Verificamos si ya existe una sesión para este usuario.
    session = await runner.session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=user_id,
    )

    # 2) Si no existe, la creamos.
    if not session:
        print(f"[ADK] Creando nueva sesión para {user_id}", flush=True)
        await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=user_id,
        )

    # 3) Ejecutamos el agente de forma asíncrona, manteniendo sesión por user_id.
    events = runner.run_async(
        user_id=user_id,
        session_id=user_id,
        new_message=content,
    )

    final_text = "Lo siento, no pude generar una respuesta."

    async for event in events:
        # Nos quedamos con la respuesta final del agente.
        if event.is_final_response():
            if event.content and event.content.parts:
                first_part = event.content.parts[0]
                if getattr(first_part, "text", None):
                    final_text = first_part.text

    print(f"[ADK] Respuesta para {user_id}: {final_text}", flush=True)
    return final_text
