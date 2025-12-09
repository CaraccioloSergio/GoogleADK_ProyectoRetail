# Retail Agent Demo (Google ADK)

Demo de un **agente de ventas y soporte para retail** construido con **Google Agent Development Kit (ADK)**.

Funcionalidades principales:

- Identificación de usuario por **email** y/o **teléfono**
- Búsqueda de productos en un **catálogo de prueba**
- Manejo de **carrito de compras** (agregar productos, ver resumen)
- Simulación de **checkout**, generando un **link de pago** que apunta a un formulario de YopLabs

Este proyecto está pensado como **POC** para usar en:
- Demos técnicas (devs)
- Demos comerciales (LinkedIn, potenciales clientes)
- Base para conectar luego con **WhatsApp** (Twilio / Meta Cloud API)

---

## Estructura

```text
retail-agent-demo/
│
├── retail_agent/
│   ├── __init__.py
│   ├── agent.py          # Definición del agente ADK y tools
│   ├── data.py           # "Base de datos" de prueba (usuarios + productos)
│   ├── cart_store.py     # Manejo de carritos en memoria
│   └── .env.example      # Ejemplo de configuración de entorno
│
├── requirements.txt
├── README.md
└── CONFIG.md             # Guía paso a paso de instalación y uso
│  
│  
└──checkout_web
    ├──index.hmtl
    ├──script.js
    └──style.css