"""
Script para regenerar el token de Google OAuth2
Ejecuta este script para re-autenticar con Google Drive y Sheets
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, TOKEN_FILE

# Scopes necesarios
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]

def regenerar_token():
    """Elimina el token actual y genera uno nuevo"""
    
    print("=" * 60)
    print("REGENERACIÓN DE TOKEN DE GOOGLE")
    print("=" * 60)
    
    # 1. Eliminar token existente si existe
    if os.path.exists(TOKEN_FILE):
        print(f"\n[1] Eliminando token expirado: {TOKEN_FILE}")
        os.remove(TOKEN_FILE)
        print("    ✓ Token eliminado")
    else:
        print(f"\n[1] No existe token anterior")
    
    # 2. Crear credenciales
    print("\n[2] Creando credenciales OAuth2...")
    client_config = {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"]
        }
    }
    
    # 3. Iniciar flujo de autenticación
    print("\n[3] Iniciando flujo de autenticación...")
    print("    ⚠️  Se abrirá tu navegador para autorizar el acceso")
    print("    ⚠️  Inicia sesión con la cuenta que tiene acceso a Google Drive y Sheets")
    
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=SCOPES
    )
    
    # Ejecutar servidor local para recibir el callback en puerto 8080
    creds = flow.run_local_server(port=8080)
    
    # 4. Guardar token
    print("\n[4] Guardando nuevo token...")
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())
    print(f"    ✓ Token guardado en: {TOKEN_FILE}")
    
    print("\n" + "=" * 60)
    print("✅ TOKEN REGENERADO EXITOSAMENTE")
    print("=" * 60)
    print("\nAhora puedes ejecutar: python app.py")

if __name__ == "__main__":
    try:
        regenerar_token()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nSi el error persiste, verifica:")
        print("1. Las credenciales en config.py (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)")
        print("2. Que las URIs de redireccion incluyan: http://localhost:8080/")
