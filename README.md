# ⚖️ LexJal — Agente de Orientación Jurídica Civil

> Agente de IA especializado en derecho civil del Estado de Jalisco y legislación federal mexicana. Orientación jurídica gratuita, sin tecnicismos, disponible en la web, WhatsApp y a través de MCP (Claude.ai / ChatGPT).

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Anthropic-Claude_Sonnet-purple.svg)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/Licencia-MIT-yellow.svg)](LICENSE)

---

## 📖 ¿Qué es LexJal?

LexJal es un agente de inteligencia artificial diseñado para brindar **orientación jurídica civil gratuita** a cualquier persona. Combina:

- **RAG (Retrieval-Augmented Generation)**: recupera artículos de la normativa oficial antes de responder, evitando alucinaciones.
- **Claude Sonnet**: genera respuestas claras, empáticas y sin jerga legal innecesaria.
- **Corpus legal oficial**: Código Civil de Jalisco, Código Civil Federal, Ley del Registro Civil, Ley del Notariado, entre otras.
- **Rate limiting inteligente**: 1 consulta gratuita al día por usuario/IP.

### Áreas de práctica cubiertas

| Área | Temas |
|------|-------|
| Familia | Divorcios, pensiones alimenticias, tutela, adopción |
| Contratos | Compraventa, arrendamiento, préstamos, donaciones |
| Sucesiones | Herencias, testamentos, intestados |
| Propiedad | Derechos sobre inmuebles, usucapión, copropiedad |
| Obligaciones | Deudas, responsabilidad civil, daños |
| Registro Civil | Actas, reconocimiento de hijos, cambio de nombre |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                   Canales de acceso                  │
│  Web (Lovable) │ Claude.ai MCP │ ChatGPT │ WhatsApp │
└────────────────────────┬────────────────────────────┘
                         │
               ┌─────────▼──────────┐
               │   FastAPI Backend   │
               │  Auth · Rate limit  │
               │  REST API · MCP     │
               └────────┬───────────┘
                        │
          ┌─────────────▼──────────────┐
          │    Agente LexJal (Claude)   │
          │  Prompts · Anti-alucinación │
          └─────────────┬──────────────┘
                        │
       ┌────────────────▼────────────────┐
       │         RAG Pipeline            │
       │  ChromaDB · Embeddings · MMR    │
       └───────────────┬─────────────────┘
                       │
       ┌───────────────▼─────────────────┐
       │         Corpus Legal            │
       │  PDFs → Chunks → Vectores       │
       │  Código Civil Jalisco           │
       │  Código Civil Federal           │
       │  + 5 leyes más                  │
       └─────────────────────────────────┘
```

---

## 🚀 Inicio rápido

### Prerrequisitos

- Python 3.12+
- Docker y Docker Compose
- API key de Anthropic

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/lexjal.git
cd lexjal
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
nano .env   # Editar con tus credenciales
```

Variables mínimas requeridas:

```env
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_PASSWORD=tu_clave_segura
SECRET_KEY=clave_secreta_larga
```

### 3. Agregar documentos legales

Coloca los PDFs de las leyes en la carpeta `legal_docs/`:

```bash
mkdir legal_docs
# Opción A: descarga automática (requiere conexión)
python ingestion/ingest.py --download --solo-prioritarios

# Opción B: descarga manual
# Descarga desde https://congresoweb.congresojal.gob.mx
# y coloca los PDFs con los nombres del mapeo en ingestion/ingest.py
```

### 4. Levantar los servicios

```bash
docker compose up -d
```

### 5. Indexar el corpus legal

```bash
docker compose exec api python ingestion/ingest.py
```

### 6. Verificar funcionamiento

```bash
# Health check
curl http://localhost:8080/health

# Prueba de consulta
curl -X POST http://localhost:8080/consulta/ \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "¿Puedo heredar sin testamento en Jalisco?"}'
```

---

## 📡 API Reference

### `POST /consulta/`

Realiza una consulta jurídica civil.

**Request:**
```json
{
  "pregunta": "¿Cuáles son mis derechos si mi casero quiere subirme la renta?",
  "historial": [],
  "canal": "web"
}
```

**Response:**
```json
{
  "id": "uuid",
  "respuesta": "Según el artículo 2432 del Código Civil de Jalisco...",
  "fuentes": [
    {
      "ley": "Código Civil del Estado de Jalisco",
      "articulo": "Artículo 2432",
      "fragmento": "..."
    }
  ],
  "tokens_usados": 1245,
  "tiempo_ms": 2300,
  "consultas_restantes": 0,
  "advertencia_limite": true
}
```

### `POST /consulta/stream`

Versión streaming (Server-Sent Events) para respuesta progresiva.

```javascript
const eventSource = new EventSource('/consulta/stream');
// Emite: { type: "sources", sources: [...] }
// Emite: { type: "token", content: "..." }
// Emite: { type: "done" }
```

### `GET /consulta/estado`

Consulta el uso diario del usuario actual.

---

## 🔌 Integración MCP (Claude.ai y ChatGPT)

LexJal implementa el Model Context Protocol (MCP) para integrarse directamente con Claude.ai y otros clientes compatibles.

### Claude.ai Desktop

1. Instalar las dependencias:
```bash
pip install -r backend/requirements.txt
```

2. Agregar en la configuración de Claude Desktop (`~/.config/claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "lexjal": {
      "command": "python",
      "args": ["-m", "backend.mcp.server"],
      "cwd": "/ruta/a/lexjal",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "REDIS_URL": "redis://localhost:6379/0",
        "CHROMA_HOST": "localhost"
      }
    }
  }
}
```

3. Reiniciar Claude Desktop. Aparecerá la herramienta `consulta_juridica_civil`.

### Herramientas MCP disponibles

| Herramienta | Descripción |
|-------------|-------------|
| `consulta_juridica_civil` | Consulta jurídica con RAG y citación de artículos |
| `estado_consultas` | Verifica consultas disponibles del día |

---

## 🌐 Integración con Lovable (Frontend Web)

El frontend en Lovable se conecta a la API REST. Ejemplo de integración:

```javascript
// En tu componente de Lovable
const response = await fetch('https://api.lexjal.com/consulta/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ pregunta: userInput })
});

const data = await response.json();
setRespuesta(data.respuesta);
setFuentes(data.fuentes);
```

Para streaming:
```javascript
const eventSource = new EventSource(`https://api.lexjal.com/consulta/stream?pregunta=${encodeURIComponent(text)}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'token') appendToChat(data.content);
  if (data.type === 'done') eventSource.close();
};
```

---

## 📱 Integración WhatsApp (Fase 2)

1. Crear una cuenta en [Meta Business Suite](https://business.facebook.com)
2. Configurar un número de WhatsApp Business
3. Agregar las variables de entorno de Meta:
```env
META_VERIFY_TOKEN=tu_token_verificacion
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
META_APP_SECRET=tu_app_secret
```
4. Registrar el router en `main.py`:
```python
from backend.api.whatsapp import router as wa_router
app.include_router(wa_router)
```
5. Configurar el webhook en Meta: `https://tu-dominio.com/whatsapp/webhook`

---

## 💳 Pagos con Stripe (Fase 3)

1. Crear cuenta en [Stripe](https://stripe.com)
2. Crear los productos/precios en el dashboard
3. Agregar variables de entorno:
```env
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```
4. Actualizar los `stripe_price_id` en `backend/api/pagos.py`
5. Registrar el router en `main.py`
6. Configurar el webhook de Stripe: `https://tu-dominio.com/pagos/webhook`

### Planes
| Plan | Precio | Consultas/día |
|------|--------|---------------|
| Gratuito | $0 | 1 |
| Básico | MXN $99/mes | 30 |
| Profesional | MXN $299/mes | Ilimitadas |

---

## 🖥️ Despliegue en VPS Hetzner

```bash
# En tu VPS (Ubuntu 24.04)
git clone https://github.com/tu-usuario/lexjal.git /opt/lexjal
cd /opt/lexjal

# Configurar dominio en el .env
LEXJAL_DOMAIN=lexjal.com ./scripts/deploy.sh
```

---

## 📂 Estructura del proyecto

```
lexjal/
├── backend/
│   ├── agent/
│   │   ├── agent.py        # Agente principal (Claude + RAG)
│   │   ├── prompts.py      # System prompts y plantillas
│   │   └── rag.py          # Pipeline RAG (ChromaDB)
│   ├── api/
│   │   ├── consultas.py    # Router principal de consultas
│   │   ├── admin.py        # Endpoints de administración
│   │   ├── whatsapp.py     # Webhook de WhatsApp (fase 2)
│   │   ├── pagos.py        # Integración Stripe (fase 3)
│   │   └── schemas.py      # Schemas Pydantic
│   ├── db/
│   │   ├── models.py       # Modelos SQLAlchemy
│   │   └── database.py     # Conexión y sesiones
│   ├── mcp/
│   │   └── server.py       # Servidor MCP (Claude.ai)
│   ├── middleware/
│   │   └── rate_limiter.py # Rate limiting (Redis)
│   ├── config.py           # Configuración central
│   ├── main.py             # App FastAPI
│   ├── requirements.txt
│   └── Dockerfile
├── ingestion/
│   └── ingest.py           # Script de ingesta de leyes
├── legal_docs/             # PDFs de leyes (no se suben a Git)
├── nginx/
│   └── nginx.conf          # Proxy reverso + SSL
├── scripts/
│   ├── deploy.sh           # Script de despliegue
│   └── init.sql            # Inicialización de DB
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🛡️ Diseño anti-alucinación

LexJal implementa múltiples capas para evitar que el agente invente información jurídica:

1. **RAG obligatorio**: el agente solo puede responder con base en el contexto recuperado.
2. **System prompt restrictivo**: instrucciones explícitas de no inventar artículos.
3. **Temperatura baja** (`0.1`): respuestas más deterministas y predecibles.
4. **Citación obligatoria**: el prompt requiere siempre citar el artículo y la ley.
5. **Mensaje de fallback**: si no hay contexto relevante, responde con una negativa honesta y dirige al usuario a un abogado real.

---

## 🧠 Prompting

El system prompt está en `backend/agent/prompts.py`. Puntos clave del diseño:

```
REGLAS ABSOLUTAS:
1. SOLO responde con base en el contexto legal proporcionado.
2. NUNCA inventes leyes, artículos o jurisprudencias.
3. SIEMPRE cita el artículo y la ley específica.
4. SIEMPRE incluye el aviso legal al final.
```

El prompt también define la estructura de respuesta:
1. Situación entendida (confirma lo que entendió)
2. Orientación jurídica (con citas)
3. Pasos sugeridos
4. Aviso legal

---

## 🤝 Contribuir

Este es un proyecto pro-bono de acceso a la justicia. Las contribuciones son bienvenidas:

1. Fork del repositorio
2. Crea una rama: `git checkout -b feature/mi-mejora`
3. Commit: `git commit -m 'feat: descripción del cambio'`
4. Push: `git push origin feature/mi-mejora`
5. Abre un Pull Request

### Ideas de contribución
- Agregar más leyes al corpus (laboral, mercantil, familiar)
- Mejorar el chunking de artículos largos
- Agregar soporte para Telegram
- Crear tests automatizados del agente
- Traducción al inglés e idiomas indígenas de Jalisco

---

## 📜 Descargo de responsabilidad

LexJal proporciona **orientación jurídica general** basada en la normativa oficial, pero **no sustituye la asesoría de un abogado certificado**. Para casos específicos, recomendamos:

- **Defensoría Pública de Jalisco**: ☎️ 33 3030-0000 | Av. Federalismo Norte 110
- **Instituto Jalisciense de Asistencia Jurídica**: www.ijaj.jalisco.gob.mx
- **Colegio de Abogados de Jalisco**: www.cabj.org.mx

---

## 📄 Licencia

MIT License. Libre para usar, modificar y distribuir con atribución.

---

*Construido con ❤️ para democratizar el acceso a la justicia en Jalisco, México.*
