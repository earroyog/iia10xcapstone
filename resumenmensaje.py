#!/usr/bin/env python3
import anthropic
import sys
from anthropic.types import MessageParam, TextBlock, ToolUnionParam, ToolUseBlock
from dotenv import load_dotenv
import asyncio

# Cargar variables de entorno
load_dotenv()

# Inicializar cliente de Anthropic
anthropic_client = anthropic.Anthropic()

async def generar_resumen(texto: str) -> str:
    """
    Genera un resumen elegante y profesional del texto usando Anthropic.
    
    Args:
        texto (str): El texto a resumir
    
    Returns:
        str: El resumen generado
    """
    try:
        # Construir el prompt para un resumen profesional y elegante
        prompt = f"""Por favor, genera un resumen elegante y profesional del siguiente texto.
        El resumen debe ser conciso pero informativo, manteniendo un estilo sofisticado y formal.
        Usa formato Markdown para mejorar la legibilidad.
        Incluye los puntos clave y mantén un tono profesional y elegante.
        Estructura el resumen de manera clara y organizada.
        No hagas referencia a que es un resumen.

        Texto a resumir:
        {texto}

        Resumen:"""

        # Generar el resumen usando Claude
        response = anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0.7,
            system="Eres un asistente experto en generar resúmenes elegantes y profesionales.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        return response.content[0].text
    except Exception as e:
        print(f"Error al generar el resumen: {str(e)}")
        return texto

async def main():
    """Función principal que maneja la entrada y salida del programa"""
    # Verificar si se proporcionó texto como argumento
    if len(sys.argv) > 1:
        texto = " ".join(sys.argv[1:])
    else:
        # Si no hay argumentos, pedir el texto por consola
        print("Por favor, introduce el texto a resumir (presiona Ctrl+D para finalizar):")
        texto = ""
        try:
            while True:
                linea = input()
                texto += linea + "\n"
        except EOFError:
            pass
    
    if not texto.strip():
        print("Error: No se proporcionó texto para resumir")
        return
    
    # Generar y mostrar el resumen
    print("\nGenerando resumen profesional y elegante...\n")
    resumen = await generar_resumen(texto)
    print("\nResumen generado:")
    print("=" * 80)
    print(resumen)
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())



