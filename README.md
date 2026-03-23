# Civilis — Agente de Orientación Jurídica Civil

> Agente de IA especializado en derecho civil y familiar del Estado de Jalisco 
> y legislación federal mexicana. Orientación jurídica gratuita, sin tecnicismos, 
> disponible en la web y a través de MCP (Claude.ai / ChatGPT).

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Anthropic-Claude_Sonnet-purple.svg)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/Licencia-MIT-yellow.svg)](LICENSE)

---

## ¿Qué es Civilis?

Civilis es un agente de inteligencia artificial desarrollado como parte del 
proyecto [IusBot](https://iusbot.online), diseñado para brindar **orientación 
jurídica civil gratuita** a cualquier persona en Jalisco. Combina:

- **RAG (Retrieval-Augmented Generation)**: recupera artículos de la normativa 
  oficial antes de responder, eliminando alucinaciones.
- **Claude Sonnet**: genera respuestas claras y sin jerga legal innecesaria.
- **Corpus legal oficial**: Código Civil de Jalisco, Código Civil Federal, 
  Código de Procedimientos Civiles, Ley del Registro Civil, Ley del Notariado, 
  Ley de Justicia Alternativa y Ley de Protección al Consumidor.
- **Rate limiting**: 1 consulta gratuita al día por usuario/IP.

### Áreas cubiertas

| Área | Temas |
|------|-------|
| Familia | Divorcios, pensiones alimenticias, tutela, adopción |
| Contratos | Compraventa, arrendamiento, préstamos, donaciones |
| Sucesiones | Herencias, testamentos, intestados |
| Propiedad | Derechos sobre inmuebles, usucapión, copropiedad |
| Obligaciones | Deudas, responsabilidad civil, daños |
| Registro Civil | Actas, reconocimiento de hijos, cambio de nombre |

---

## Demo

Civilis está disponible en producción:

- **Chat web**: [civilis.iusbot.online](https://civilis.iusbot.online)
- **Plataforma**: [iusbot.online/agentes](https://iusbot.online/agentes)

---

## Arquitectura
```
┌─────────────────────────────────────────┐
│            Canales de acceso            │
│   iusbot.online (Lovable) │ MCP (beta)  │
└──────────────────┬──────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   FastAPI Backend   │
         │  Auth · Rate limit  │
         │  REST API · MCP     │
         └────────┬────────────┘
                  │
     ┌────────────▼─────────────┐
     │    Agente Civilis         │
     │  Claude Sonnet · Prompts  │
     │  Anti-alucinación         │
     └────────────┬──────────────┘
                  │
     ┌────────────▼──────────────┐
     │       RAG Pipeline        │
     │  ChromaDB · Embeddings    │
     │  paraphrase-multilingual  │
     └────────────┬──────────────┘
                  │
     ┌────────────▼──────────────┐
     │       Corpus Legal        │
     │  8 PDFs · 7,589 chunks    │
     │  Legislación Jalisco +    │
     │  Federal                  │
     └───────────────────────────┘
```

---

## Inicio rápido

### Prerrequisitos

- Python 3.12+
- Docker y Docker Compose
- API key de Anthropic

### 1. Clonar el repositorio
```bash
git clone https://github.com/DanielMasierra/civilis.git
cd civilis
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
nano .env
```

Variables mínimas requeridas:
```env
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_PASSWORD=tu_clave_segura
SECRET_KEY=clave_secreta_larga
```

### 3. Agregar documentos legales

Coloca los PDFs en `legal_docs/`:
```
codigo_civil_federal.pdf
codigo_civil_jalisco.pdf
codigo_procedimientos_civiles_jalisco.pdf
codigo_nacional_procedimientos_civiles_familiares.pdf
ley_justicia_alternativa_jalisco.pdf
ley_notariado_jalisco.pdf
ley_registro_civil_jalisco.pdf
ley_proteccion_consumidor.pdf
```

### 4. Levantar los servicios
```bash
docker compose up -d
```

### 5. Indexar el corpus
```bash
docker compose exec api python backend/ingest.py
```

### 6. Verificar
```bash
curl http://localhost:8082/health

curl -X POST http://localhost:8082/consulta/ \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "¿Puedo heredar sin testamento en Jalisco?", "usuario_id": "test"}'
```

---

## API Reference

### `POST /consulta/`
```json
// Request
{
  "pregunta": "¿Cuáles son mis derechos si mi casero quiere subirme la renta?",
  "usuario_id": "usuario@correo.com"
}

// Response
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
  "tokens_usados": 3241,
  "tiempo_ms": 10676,
  "consultas_restantes": 0,
  "advertencia_limite": true
}
```

### Rutas disponibles

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/consulta/` | POST | Consulta jurídica principal |
| `/consulta/stream` | POST | Respuesta en streaming (SSE) |
| `/consulta/estado` | GET | Consultas disponibles del usuario |
| `/consulta/bienvenida` | GET | Mensaje de bienvenida |
| `/admin/corpus/stats` | GET | Estadísticas del corpus |
| `/health` | GET | Estado del servicio |

---

## Diseño anti-alucinación

1. **RAG obligatorio**: solo responde con base en el contexto recuperado.
2. **System prompt restrictivo**: instrucciones explícitas de no inventar artículos.
3. **Temperatura baja** (`0.1`): respuestas deterministas.
4. **Citación obligatoria**: siempre cita el artículo y la ley.
5. **Fallback honesto**: si no hay contexto relevante, lo dice y dirige a instituciones reales.

---

## Infraestructura de producción

- **Servidor**: Hetzner CCX13 — 2 vCPU dedicados, 8GB RAM
- **OS**: Ubuntu 24.04
- **Puerto**: 8082 (interno), expuesto vía Nginx
- **Dominio**: civilis.iusbot.online (SSL via Certbot)
- **Embeddings**: paraphrase-multilingual-mpnet-base-v2 (CPU, local)
- **Coexiste con**: n8n (5678), tesisbot-mcp (3001)

---

## Estructura del proyecto
```
civilis/
├── backend/
│   ├── agent/
│   │   ├── agent.py        # Agente principal (Claude + RAG)
│   │   ├── prompts.py      # System prompts
│   │   └── rag.py          # Pipeline RAG (ChromaDB)
│   ├── api/
│   │   ├── consultas.py    # Router principal
│   │   ├── admin.py        # Endpoints de administración
│   │   ├── whatsapp.py     # WhatsApp (fase 2)
│   │   ├── pagos.py        # Stripe (fase 3)
│   │   └── schemas.py      # Schemas Pydantic
│   ├── db/
│   │   ├── models.py
│   │   └── database.py
│   ├── mcp/
│   │   └── server.py       # Servidor MCP
│   ├── middleware/
│   │   └── rate_limiter.py
│   ├── ingest.py           # Ingesta de corpus legal
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── legal_docs/             # PDFs (no se suben a Git)
├── docker-compose.yml
└── README.md
```

---

## Roadmap

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 — Civilis web | ✅ | Chat en civilis.iusbot.online |
| 1 — IusBot landing | ✅ | Plataforma en iusbot.online |
| 2 — MCP Civilis | ⏳ | Integración con Claude Desktop |
| 2 — WhatsApp | ⏳ | Chatbot para reducir fricción |
| 3 — Generación de documentos | ⏳ | Escritos para tribunales de Jalisco |
| 3 — Más agentes | ⏳ | Laboral, mercantil, familiar |
| 4 — Planes de pago | ⏳ | Stripe, acceso extendido |

---

## Contribuir

Este es un proyecto pro-bono de acceso a la justicia. Las contribuciones son bienvenidas:

1. Fork del repositorio
2. Crea una rama: `git checkout -b feature/mi-mejora`
3. Commit: `git commit -m 'feat: descripción'`
4. Push y abre un Pull Request

### Ideas de contribución
- Agregar más leyes al corpus (laboral, mercantil, familiar)
- Mejorar el chunking de artículos largos
- Agregar soporte para Telegram
- Traducción a lenguas indígenas de Jalisco
- Tests automatizados del agente

---

## Descargo de responsabilidad

Civilis proporciona **orientación jurídica general** basada en normativa oficial, 
pero **no sustituye la asesoría de una persona especialista en derecho**. 
Para casos específicos:

- **Procuraduría Social del Estado de Jalisco**: +52 33 3030 2900
- **Defensoría Pública de Jalisco**: Av. Federalismo Norte 110
- **Instituto Jalisciense de Asistencia Jurídica**: ijaj.jalisco.gob.mx

---

## Contacto

- Proyecto: [iusbot.online](https://iusbot.online)
- Correo: contacto@iusbot.online
- GitHub: [DanielMasierra](https://github.com/DanielMasierra)

---

*Construido en Guadalajara para democratizar el acceso a la justicia en Jalisco.*
