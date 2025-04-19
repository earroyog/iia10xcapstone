#!/usr/bin/env python3
import asyncio
from dataclasses import dataclass, field
from typing import Union, cast
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime

import anthropic
from anthropic.types import MessageParam, TextBlock, ToolUnionParam, ToolUseBlock
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from conectar_gmail import GmailSender
from resumenmensaje import generar_resumen


load_dotenv()

anthropic_client = anthropic.AsyncAnthropic()

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["./mcp_server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)

@dataclass
class Chat:
    messages: list[MessageParam] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(datetime.now().strftime("%Y%m%d_%H%M%S")))

    system_prompt: str = """Eres un asistente experto en SQLite. 
    Tu trabajo es utilizar las herramientas disponibles para ejecutar consultas SQL y proporcionar los resultados al usuario.
    Debes responder siempre en español y ser claro y conciso en tus explicaciones."""

    def __post_init__(self):
        # Inicializar ChromaDB
        self.chroma_client = chromadb.Client(Settings(
            persist_directory="./chroma_db",
            anonymized_telemetry=False
        ))
        self.collection = self.chroma_client.get_or_create_collection(
            name=f"mcp_prompts_{self.session_id}",
            metadata={"description": f"Prompts de la sesión MCP {self.session_id}"}
        )

    async def _save_prompt(self, role: str, content: str):
        """Guarda un prompt en ChromaDB"""
        try:
            metadata = {
                'session_id': self.session_id,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'role': role
            }
            
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            print(f"Error al guardar prompt: {str(e)}")

    async def _generate_summary(self):
        """Genera un resumen de los prompts guardados en ChromaDB"""
        try:
            # Obtener todos los prompts de la colección
            results = self.collection.get()
            
            if not results or not results['documents']:
                return "No hay prompts guardados en la base de datos."
            
            # Organizar los prompts por rol
            prompts_by_role = {}
            for i, role in enumerate(results['metadatas']):
                role_type = role['role']
                if role_type not in prompts_by_role:
                    prompts_by_role[role_type] = []
                prompts_by_role[role_type].append({
                    'timestamp': role['timestamp'],
                    'content': results['documents'][i]
                })
            
            # Generar el resumen
            summary = "\n=== RESUMEN DE LA SESIÓN ===\n"
            summary += f"Sesión ID: {self.session_id}\n"
            summary += f"Total de prompts: {len(results['documents'])}\n\n"
            
            # Mostrar prompts por rol
            for role, prompts in prompts_by_role.items():
                summary += f"\n--- {role.upper()} PROMPTS ({len(prompts)}) ---\n"
                for prompt in prompts:
                    summary += f"\n[{prompt['timestamp']}]\n{prompt['content']}\n"
            
            summary += "\n=== FIN DEL RESUMEN ===\n"
            # Crear instancia
            sender = GmailSender()
            # Enviar mensaje
            resumen = await generar_resumen(summary)
            sender.send_message(resumen)
            return resumen
            
        except Exception as e:
            return f"Error al generar el resumen: {str(e)}"

    async def process_query(self, session: ClientSession, query: str) -> None:
        # Verificar si el usuario quiere terminar
        if query.lower() == 'fin':
            summary = await self._generate_summary()
            print(summary)
            return

        # Guardar el prompt del usuario
        await self._save_prompt("user", query)

        response = await session.list_tools()
        available_tools: list[ToolUnionParam] = [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

        # Initial Claude API call
        res = await anthropic_client.messages.create(
            model="claude-3-5-sonnet-latest",
            system=self.system_prompt,
            max_tokens=8000,
            messages=self.messages,
            tools=available_tools,
        )

        assistant_message_content: list[Union[ToolUseBlock, TextBlock]] = []
        for content in res.content:
            if content.type == "text":
                assistant_message_content.append(content)
                print(content.text)
                # Guardar la respuesta del asistente
                await self._save_prompt("assistant", content.text)
            elif content.type == "tool_use":
                tool_name = content.name
                tool_args = content.input

                # Execute tool call
                result = await session.call_tool(tool_name, cast(dict, tool_args))

                assistant_message_content.append(content)
                self.messages.append(
                    {"role": "assistant", "content": assistant_message_content}
                )
                self.messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": getattr(result.content[0], "text", ""),
                            }
                        ],
                    }
                )
                # Get next response from Claude
                res = await anthropic_client.messages.create(
                    model="claude-3-7-sonnet-latest",
                    max_tokens=8000,
                    messages=self.messages,
                    tools=available_tools,
                )
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": getattr(res.content[0], "text", ""),
                    }
                )
                response_text = getattr(res.content[0], "text", "")
                print(response_text)
                # Guardar la respuesta del asistente
                await self._save_prompt("assistant", response_text)

    async def chat_loop(self, session: ClientSession):
        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == 'fin':
                await self.process_query(session, query)
                break
                
            self.messages.append(
                MessageParam(
                    role="user",
                    content=query,
                )
            )

            await self.process_query(session, query)

    async def run(self):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                # Guardar el prompt del sistema
                await self._save_prompt("system", self.system_prompt)
                await self.chat_loop(session)

chat = Chat()

asyncio.run(chat.run())
