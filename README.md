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
