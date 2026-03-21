# 🧠 LexJal — Documentación de Prompting

Este documento describe el proceso de diseño del system prompt del agente y
las decisiones técnicas tomadas para garantizar respuestas precisas, empáticas
y sin alucinaciones.

---

## Filosofía del prompt

El prompt de LexJal resuelve una tensión fundamental: un modelo de lenguaje tiene
el conocimiento jurídico necesario para responder, pero sin restricciones puede
**inventar artículos que no existen**. El diseño del prompt ataca este problema
desde múltiples ángulos.

---

## Versión final del system prompt

```
Eres LexJal, el mejor orientador jurídico en materia civil de México,
especializado en el Código Civil del Estado de Jalisco y la legislación federal.
Tu misión es brindar orientación jurídica gratuita, comprensible y útil para
cualquier persona, sin importar su nivel de estudios.

## Tu forma de comunicarte
- Habla de forma clara, directa y amigable. Como si le explicaras a un familiar.
- Evita la jerga jurídica innecesaria. Si debes usar un término técnico, explícalo
  inmediatamente con palabras sencillas.
- Sé empático: quien te consulta probablemente está pasando por una situación difícil.
- No te extiendas más de lo necesario. Responde con precisión.

## Reglas absolutas — nunca las rompas
1. SOLO responde con base en el contexto legal que se te proporciona.
   Si la información no está en ese contexto, dilo claramente.
2. NUNCA inventes leyes, artículos, criterios o jurisprudencias. Si no encuentras
   la respuesta, di: "No encontré información específica sobre este tema en la
   normativa que tengo disponible. Te recomiendo acudir con un abogado o a la
   Defensoría Pública del Estado de Jalisco."
3. SIEMPRE cita el artículo y la ley en que basas tu respuesta.
4. SIEMPRE incluye al final: "⚠️ Esta es una orientación general y no sustituye
   la asesoría de un abogado certificado."
5. Si la pregunta no es sobre derecho civil, indícalo y orienta sobre dónde
   puede encontrar ayuda.

## Estructura de tu respuesta
1. Situación entendida (1-2 líneas)
2. Orientación jurídica (con artículos citados)
3. Pasos sugeridos
4. Aviso legal

## Contexto legal disponible
{context}

Consulta: {question}
```

---

## Iteraciones del prompt

### v0.1 — Prompt básico (descartado)
```
Eres un abogado experto en derecho civil mexicano. Responde la siguiente pregunta: {question}
```
**Problema**: alucinaba artículos, usaba jerga legal, no citaba fuentes.

### v0.2 — Con instrucción de no inventar
```
Eres un abogado experto. NO inventes artículos. Pregunta: {question}
```
**Problema**: el modelo seguía generando artículos plausibles pero inexistentes.
La instrucción negativa sola no funciona bien.

### v0.3 — Contexto RAG + instrucción
```
Con base ÚNICAMENTE en el siguiente contexto legal:
{context}

Responde: {question}
```
**Mejora**: redujo drásticamente las alucinaciones.
**Problema pendiente**: respuestas demasiado técnicas, sin empatía.

### v1.0 — Final (el que está implementado)
Agrega:
- Sección de personalidad ("como si le explicaras a un familiar")
- Reglas numeradas y absolutas
- Estructura de respuesta fija
- Mensaje de fallback específico
- Temperatura 0.1 para consistencia

---

## Parámetros del modelo

| Parámetro | Valor | Razón |
|-----------|-------|-------|
| `model` | `claude-sonnet-4-20250514` | Balance costo/calidad |
| `max_tokens` | 2048 | Suficiente para respuestas detalladas |
| `temperature` | 0.1 | Respuestas predecibles y precisas |

**¿Por qué temperatura baja?**
En un contexto jurídico, la creatividad es un problema. Queremos que el modelo
se "aferre" al contexto recuperado, no que "explore" alternativas. 0.1 es el
punto donde el modelo sigue siendo fluido pero extremadamente conservador.

---

## Diseño del RAG

### Chunking de textos legales

Los textos jurídicos tienen estructura natural:
- Títulos → Capítulos → Artículos → Párrafos

El splitter prioriza estas divisiones:
```python
separators=[
    "\nArtículo", "\nARTÍCULO",
    "\nCapítulo", "\nCAPÍTULO",
    "\n\n", "\n", ". ",
]
```

**chunk_size = 800** — los artículos del Código Civil de Jalisco tienen en promedio
400-600 palabras. Un chunk de 800 tokens captura el artículo completo más su contexto.

**chunk_overlap = 150** — evita que un artículo quede partido entre dos chunks sin
contexto del anterior.

### Embeddings

Modelo elegido: `paraphrase-multilingual-mpnet-base-v2`
- 100% local (sin costo de API adicional)
- Excelente para español jurídico
- 768 dimensiones, suficiente para este dominio

### Búsqueda MMR (Maximum Marginal Relevance)

En lugar de top-K simple, usamos MMR para:
1. Recuperar los documentos más relevantes
2. **Evitar redundancia**: si hay 5 artículos sobre arrendamiento, no devuelve los 5;
   devuelve los más distintos entre sí pero relevantes para la consulta.

```python
retriever = vs.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 6, "fetch_k": 20}
)
```

---

## Pruebas del agente

### Casos de prueba básicos

| Pregunta | Resultado esperado | Anti-alucinación |
|----------|-------------------|-----------------|
| "¿Puedo heredar sin testamento?" | Cita artículos sobre sucesión intestada del CCJ | ✅ |
| "¿Cuánto puede subir la renta mi casero?" | Cita Ley de Arrendamiento Jalisco | ✅ |
| "¿Qué pasa si no reconozco a mi hijo?" | Cita artículos de filiación del CCJ | ✅ |
| "¿Cómo me defiendo de una denuncia penal?" | Indica que es materia penal, no civil | ✅ |
| "¿Cuántos años tiene de prisión el robo?" | Indica especialidad civil, orienta a donde ir | ✅ |
| "¿Qué dice el artículo 999999 del CC?" | Dice que no encontró información | ✅ |

### Prueba de alucinación (verificación manual)

Después de cada consulta, verificar manualmente que:
1. El artículo citado **existe** en la ley mencionada
2. El número de artículo **coincide** con el contenido citado
3. La ley mencionada **existe** con ese nombre exacto

---

## Convención de nombres de archivos PDF

Para que el sistema mapee correctamente los documentos a sus nombres de ley:

| Nombre de archivo | Ley mapeada |
|------------------|-------------|
| `codigo_civil_jalisco.pdf` | Código Civil del Estado de Jalisco |
| `codigo_civil_federal.pdf` | Código Civil Federal |
| `codigo_procedimientos_civiles_jalisco.pdf` | Código de Procedimientos Civiles de Jalisco |
| `ley_familia_jalisco.pdf` | Código Familiar del Estado de Jalisco |
| `ley_registro_civil_jalisco.pdf` | Ley del Registro Civil de Jalisco |
| `ley_notariado_jalisco.pdf` | Ley del Notariado de Jalisco |
| `ley_arrendamiento_jalisco.pdf` | Ley de Arrendamiento Inmobiliario de Jalisco |

Archivos con nombres no reconocidos se mapean automáticamente con el nombre limpiado del archivo.

---

## Lecciones aprendidas

1. **RAG es obligatorio** en aplicaciones jurídicas. Sin él, el modelo siempre alucina.
2. **Temperatura baja** (0.1) es no negociable en contextos de precisión legal.
3. **El fallback honesto** ("no encontré información") genera más confianza que una
   respuesta fabricada que parece correcta.
4. **La empatía en el prompt** es tan importante como las reglas técnicas. Los usuarios
   en problemas legales están bajo estrés; el tono importa.
5. **MMR > top-K** para corpus jurídicos: evita devolver 5 artículos redundantes
   sobre el mismo tema cuando la pregunta abarca varios temas.
