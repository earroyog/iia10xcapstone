#!/usr/bin/env python3


import socket
import threading
import base64
import json
import os
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime

# Si modificas estos SCOPES, elimina el archivo token.json
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def setup_oauth_credentials():
    """Configura las credenciales de OAuth2 para Gmail"""
    print("Configurando credenciales de OAuth2 para Gmail...")
    
    # Verificar si ya existe el archivo de credenciales
    if os.path.exists('token.json'):
        print("El archivo token.json ya existe.")
        return
    
    if not os.path.exists('credentials.json'):
        print("\nPor favor, sigue estos pasos:")
        print("1. Ve a https://console.cloud.google.com/")
        print("2. Crea un nuevo proyecto o selecciona uno existente")
        print("3. Habilita la API de Gmail")
        print("4. Ve a 'Credenciales' y crea un nuevo ID de cliente OAuth 2.0")
        print("5. Descarga el archivo JSON de credenciales")
        print("6. Renombra el archivo descargado a 'credentials.json'")
        print("7. Coloca el archivo en el mismo directorio que este script")
        
        input("\nPresiona Enter cuando hayas completado estos pasos...")
        
        if not os.path.exists('credentials.json'):
            print("Error: No se encontró el archivo credentials.json")
            return
    
    try:
        # Crear el flujo de autenticación
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Guardar las credenciales para uso futuro
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        
        print("Credenciales configuradas correctamente!")
    except Exception as e:
        print(f"Error durante la configuración: {str(e)}")
        print("Por favor, verifica que el archivo credentials.json tenga el formato correcto.")
        print("El archivo debe contener: client_id, project_id, auth_uri, token_uri, auth_provider_x509_cert_url, client_secret y redirect_uris")

class GmailSender:
    def __init__(self, credentials_file='token.json'):
        """Inicializa el servicio de Gmail con las credenciales proporcionadas"""
        self.credentials_file = credentials_file
        self.gmail_service = self._get_gmail_service()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _get_gmail_service(self):
        """Obtiene el servicio de Gmail usando las credenciales"""
        creds = None
        
        # Cargar credenciales desde el archivo token.json
        if os.path.exists(self.credentials_file):
            try:
                creds = Credentials.from_authorized_user_file(self.credentials_file, SCOPES)
            except Exception as e:
                print(f"Error al cargar token.json: {str(e)}")
                creds = None
        
        # Si no hay credenciales válidas disponibles, el usuario debe iniciar sesión
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error al refrescar credenciales: {str(e)}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error durante la autenticación: {str(e)}")
                    raise
            
            # Guardar las credenciales para la próxima ejecución
            with open(self.credentials_file, 'w') as token:
                token.write(creds.to_json())
    
        return build('gmail', 'v1', credentials=creds)

    def send_message(self, message: str):
        """Envía un mensaje por correo electrónico
        
        Args:
            message (str): Contenido del mensaje a enviar
        """
        try:
            # Crear el asunto con sesión y timestamp
            subject = f"Sesión {self.session_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Crear el mensaje
            email_message = MIMEMultipart()
            email_message['to'] = 'earroyog@gmail.com'
            email_message['from'] = 'earroyog@gmail.com'
            email_message['subject'] = subject
            
            email_message.attach(MIMEText(message, 'plain'))
            
            # Codificar el mensaje
            raw_message = base64.urlsafe_b64encode(email_message.as_bytes()).decode('utf-8')
            
            # Enviar el correo
            self.gmail_service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            print("Correo enviado exitosamente")
            return True
        except Exception as e:
            print(f"Error al enviar el correo: {str(e)}")
            return False

class GmailMCPServer:
    def __init__(self, host='0.0.0.0', port=9000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.credentials_file = 'credentials.json'
        


    def handle_client(self, client_socket):
        try:
            # Recibir datos del cliente
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
            
            # Procesar los datos (formato esperado: DESTINATARIO|ASUNTO|CUERPO)
            parts = data.split('|', 2)
            if len(parts) != 3:
                response = "ERROR: Formato incorrecto. Use: DESTINATARIO|ASUNTO|CUERPO"
                client_socket.send(response.encode('utf-8'))
                return
            
            recipient, subject, body = parts
            
            # Intentar enviar el correo con OAuth2
            try:
                self.send_email_oauth2(recipient, subject, body)
                response = "ÉXITO: Correo enviado correctamente con OAuth2"
            except Exception as e:
                response = f"ERROR: No se pudo enviar el correo - {str(e)}"
            
            # Enviar respuesta al cliente
            client_socket.send(response.encode('utf-8'))
            
        except Exception as e:
            print(f"Error al manejar cliente: {e}")
        finally:
            client_socket.close()

    def get_credentials(self):
        """Obtener credenciales OAuth2 para la API de Gmail."""
        creds = None
        
        # El archivo token.json almacena los tokens de acceso y actualización del usuario
        if os.path.exists('token.json'):
            try:
                with open('token.json', 'r') as token_file:
                    token_data = json.load(token_file)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            except Exception as e:
                print(f"Error al cargar token.json: {e}")
                creds = None
        
        # Si no hay credenciales válidas disponibles, el usuario debe iniciar sesión
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"No se encontró el archivo {self.credentials_file}. " 
                        "Descárgalo de la consola de Google Cloud.")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Guardar las credenciales para la próxima ejecución
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        return creds

    def send_email_oauth2(self, recipient, subject, body):
        """Envía un correo electrónico usando la API de Gmail con OAuth2 directamente via HTTP."""
        creds = self.get_credentials()
        
        # Crear el mensaje de correo electrónico
        message = MIMEMultipart()
        message['to'] = recipient
        message['subject'] = subject
        message.attach(MIMEText(body))
        
        # Convertir a formato raw para la API de Gmail
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Preparar la petición HTTP
        url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
        headers = {
            'Authorization': f'Bearer {creds.token}',
            'Content-Type': 'application/json'
        }
        data = {
            'raw': raw_message
        }
        
        # Enviar la petición HTTP
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            message_id = response.json().get('id')
            print(f"Mensaje enviado con ID: {message_id}")
            return message_id
        else:
            error_msg = f"Error al enviar correo: {response.status_code} - {response.text}"
            print(error_msg)
            raise Exception(error_msg)


if __name__ == "__main__":
    try:
        # Verificar si necesitamos configurar las credenciales
        if not os.path.exists('token.json'):
            setup_oauth_credentials()
            exit()
        
        # Crear instancia del sender
        sender = GmailSender()
        
        # Enviar mensaje de prueba
        sender.send_message("Este es un mensaje de prueba")
    except Exception as e:
        print(f"Error: {str(e)}")