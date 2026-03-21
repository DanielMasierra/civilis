-- ============================================================
-- LexJal — Inicialización de base de datos PostgreSQL
-- Se ejecuta automáticamente al primer inicio del contenedor
-- ============================================================

-- Extensión para UUID nativos
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extensión para búsqueda de texto (opcional, para historial)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Índice de texto para búsquedas en preguntas del historial
-- (se crea después de que SQLAlchemy genere las tablas)

-- Función para actualizar automáticamente el campo actualizado_en
CREATE OR REPLACE FUNCTION update_actualizado_en()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
