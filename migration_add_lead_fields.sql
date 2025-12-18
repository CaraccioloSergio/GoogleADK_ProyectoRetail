-- Migración: Agregar campos para recolección de leads
-- Fecha: 2025-12-18
-- Descripción: Agrega campos a la tabla users para capturar info de negocio

-- Agregar columnas para lead capture
ALTER TABLE users ADD COLUMN profession TEXT;
ALTER TABLE users ADD COLUMN company TEXT;
ALTER TABLE users ADD COLUMN industry TEXT;
ALTER TABLE users ADD COLUMN comments TEXT;
ALTER TABLE users ADD COLUMN lead_source TEXT DEFAULT 'whatsapp_demo';

-- Verificar
SELECT 
    id, 
    name, 
    email, 
    profession, 
    company, 
    industry,
    lead_source,
    created_at 
FROM users 
LIMIT 1;
