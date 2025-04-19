#!/usr/bin/env python3
import sqlite3
import os
from loguru import logger
from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any
import json
import sys
import signal

# Configurar logger
logger.remove()  # Remover el logger por defecto
logger.add(sys.stderr, level="INFO")  # Añadir logger a stderr
logger.add("mcp_server.log", rotation="500 MB", level="DEBUG")

print("Iniciando servidor MCP...", file=sys.stderr, flush=True)
logger.info("Iniciando servidor MCP...")

# Manejar señales para cierre limpio
def handle_signal(signum, frame):
    logger.info(f"Recibida señal {signum}, cerrando servidor...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# Create an MCP server
mcp = FastMCP("SQLiteServer")

# Asegurarse de que la base de datos existe
DB_PATH = os.path.join(os.path.dirname(__file__), "resources/database.db")
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    # Crear una tabla de ejemplo
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ejemplo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        descripcion TEXT
    )
    """)
    # Insertar algunos datos de ejemplo
    cursor.execute("""
    INSERT INTO ejemplo (nombre, descripcion) VALUES 
    ('Ejemplo 1', 'Primera entrada de ejemplo'),
    ('Ejemplo 2', 'Segunda entrada de ejemplo')
    """)
    conn.commit()
    conn.close()
    logger.info(f"Created new database with example table at {DB_PATH}")

@mcp.tool()
def query_data(sql: str) -> str:
    """Ejecuta consultas SQL de forma segura y devuelve los resultados formateados"""
    logger.info(f"Executing SQL query: {sql}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # Si es un SELECT, obtener los resultados
        if sql.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            if not results:
                return "La consulta no devolvió resultados."
            
            # Obtener nombres de columnas
            columns = [description[0] for description in cursor.description]
            
            # Formatear resultados como tabla
            output = []
            output.append(" | ".join(columns))  # Encabezados
            output.append("-" * (len(output[0]) + 2))  # Línea separadora
            
            for row in results:
                output.append(" | ".join(str(value) for value in row))
            
            return "\n".join(output)
        else:
            # Para INSERT, UPDATE, DELETE, etc.
            conn.commit()
            affected = cursor.rowcount
            return f"Operación ejecutada con éxito. Filas afectadas: {affected}"
            
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return f"Error en la consulta: {str(e)}"
    finally:
        conn.close()

@mcp.tool()
def list_tables() -> str:
    """Lista todas las tablas en la base de datos"""
    logger.info("Listing all tables")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables:
            return "No hay tablas en la base de datos."
        
        return "Tablas disponibles:\n" + "\n".join(f"- {table[0]}" for table in tables)
    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        return f"Error al listar tablas: {str(e)}"
    finally:
        conn.close()

@mcp.tool()
def describe_table(table_name: str) -> str:
    """Describe la estructura de una tabla específica"""
    logger.info(f"Describing table: {table_name}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        if not columns:
            return f"La tabla '{table_name}' no existe."
        
        output = [f"Estructura de la tabla '{table_name}':\n"]
        output.append("Columna | Tipo | Not Null | Default | Primary Key")
        output.append("-" * 50)
        
        for col in columns:
            output.append(f"{col[1]} | {col[2]} | {col[3]} | {col[4]} | {col[5]}")
        
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Error describing table: {str(e)}")
        return f"Error al describir la tabla: {str(e)}"
    finally:
        conn.close()

@mcp.prompt()
def example_prompt(code: str) -> str:
    return f"Please review this code:\n\n{code}"

if __name__ == "__main__":
    try:
        logger.info("Starting SQLite MCP server on stdio...")
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
        # Flush stdout y stderr
        sys.stdout.flush()
        sys.stderr.flush()
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        sys.exit(1)
