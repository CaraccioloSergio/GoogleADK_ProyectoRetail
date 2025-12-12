# start_milo_dev.ps1
# Levanta checkout, backoffice, whatsapp_server y ngrok en ventanas separadas

$projectRoot = "C:\Users\Sergio\Desktop\Dev\retail-agent-demo"

# 1) Checkout - http.server en 8001
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$projectRoot\checkout_web`"; `"$projectRoot\.venv\Scripts\Activate.ps1`"; python -m http.server 8001"
)

# 2) Backoffice FastAPI en 8000
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$projectRoot`"; `"$projectRoot\.venv\Scripts\Activate.ps1`"; uvicorn backoffice_app:app --reload --port 8000"
)

# 3) WhatsApp server en 9000
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$projectRoot`"; `"$projectRoot\.venv\Scripts\Activate.ps1`"; uvicorn whatsapp_server:app --reload --port 9001"
)

# 4) Ngrok apuntando al WhatsApp server
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$projectRoot`"; ngrok http 9001"
)

