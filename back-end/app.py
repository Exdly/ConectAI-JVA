"""
Servidor Principal - IESTP Juan Velasco Alvarado
=================================================
Backend Flask para el chatbot de trámites académicos.
"""

from flask import Flask, request, jsonify, redirect, render_template
from flask_cors import CORS
import traceback
import html
import re
import os
import sys

# Obtener el directorio base del archivo app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Agregar el directorio base al path de Python para imports
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Constantes de validación
MAX_MESSAGE_LENGTH = 2000

def sanitize_input(text):
    """Sanitiza el input del usuario para prevenir inyección de código."""
    if not isinstance(text, str):
        return ""
    sanitized = html.escape(text)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
    return sanitized.strip()

from config import SERVER_PORT, DEBUG_MODE, ALLOWED_ORIGINS
from google_drive import (
    get_drive_manager, 
    get_authorization_url, 
    exchange_code_for_tokens,
    is_authenticated
)
from google_sheets import get_sheets_manager
from ai_manager import get_ai_manager
from web_scraper import get_web_scraper

# Configurar Flask con templates y static folders
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
    static_url_path='/static'
)

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# =============================================================================
# ENDPOINTS DE AUTENTICACIÓN
# =============================================================================

@app.route('/')
def index():
    """Página principal del chatbot."""
    return render_template('index.html')


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Verifica si el servidor está autenticado con Google."""
    authenticated = is_authenticated()
    return jsonify({
        "authenticated": authenticated,
        "message": "Autenticado con Google" if authenticated else "No autenticado"
    })


@app.route('/api/auth/url', methods=['GET'])
def auth_url():
    """Obtiene la URL para autorizar la aplicación con Google."""
    url = get_authorization_url()
    return jsonify({
        "success": True,
        "auth_url": url
    })


@app.route('/oauth2callback', methods=['GET'])
def oauth_callback():
    """Callback de OAuth 2.0."""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"""
        <html>
        <head><title>Error de Autorización</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #f44336;">Error de Autorización</h1>
            <p>No se pudo completar la autorización: {error}</p>
        </body>
        </html>
        """
    
    if not code:
        return """
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #f44336;">Error</h1>
            <p>No se recibió el código de autorización.</p>
        </body>
        </html>
        """
    
    tokens = exchange_code_for_tokens(code)
    
    if 'access_token' in tokens:
        drive_manager = get_drive_manager()
        drive_manager.reconnect()
        
        sheets_manager = get_sheets_manager()
        sheets_manager.reconnect()
        
        return """
        <html>
        <head><title>Autorización Exitosa</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #4caf50;">¡Autorización Exitosa!</h1>
            <p>La aplicación ha sido autorizada correctamente.</p>
            <p>Ahora puedes cerrar esta ventana y usar el chatbot.</p>
            <script>
                if (window.opener) {
                    window.opener.postMessage('oauth_success', '*');
                }
                setTimeout(function() { window.close(); }, 3000);
            </script>
        </body>
        </html>
        """
    else:
        error_msg = tokens.get('error_description', tokens.get('error', 'Error desconocido'))
        return f"""
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #f44336;">Error al obtener tokens</h1>
            <p>{error_msg}</p>
        </body>
        </html>
        """


# =============================================================================
# ENDPOINTS PRINCIPALES
# =============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que el servidor está funcionando."""
    return jsonify({
        "status": "ok",
        "message": "Servidor del Asistente IESTP JVA funcionando correctamente",
        "authenticated": is_authenticated()
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint principal para procesar mensajes del chatbot."""
    try:
        if not is_authenticated():
            return jsonify({
                "success": False,
                "error": "not_authenticated",
                "message": "El servidor no está autenticado con Google. Por favor, autoriza primero."
            }), 401
        
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                "success": False,
                "error": "No se proporcionó un mensaje"
            }), 400
        
        raw_message = data['message']
        
        if not isinstance(raw_message, str):
            return jsonify({
                "success": False,
                "error": "El mensaje debe ser texto"
            }), 400
        
        user_message = sanitize_input(raw_message)
        
        if not user_message:
            return jsonify({
                "success": False,
                "error": "El mensaje está vacío"
            }), 400
        
        if len(user_message) > MAX_MESSAGE_LENGTH:
            return jsonify({
                "success": False,
                "error": f"El mensaje excede el límite de {MAX_MESSAGE_LENGTH} caracteres"
            }), 400
        
        conversation_history = data.get('history', [])
        if not isinstance(conversation_history, list):
            conversation_history = []
        
        print(f"\n[API] Nueva consulta: {user_message[:100]}...")
        
        drive_manager = get_drive_manager()
        sheets_manager = get_sheets_manager()
        ai_manager = get_ai_manager()
        web_scraper = get_web_scraper()
        
        query_type = ai_manager.classify_query(user_message)
        print(f"[API] Tipo de consulta: {query_type}")
        
        pdf_context = drive_manager.search_in_documents(user_message)
        if not pdf_context:
            print("[API] ADVERTENCIA: No se pudo obtener contexto de PDFs")
        
        web_context = web_scraper.get_all_website_content()
        
        response = ai_manager.generate_response(
            user_message=user_message,
            pdf_context=pdf_context,
            web_context=web_context,
            conversation_history=conversation_history
        )
        
        row_number = 0
        
        if response is None:
            response = (
                "Lo siento, estoy teniendo dificultades técnicas para procesar tu consulta en este momento. "
                "Por favor, intenta nuevamente en unos segundos."
            )
            status = "error_ia"
            print("[API] Error de IA - NO se guardará en Google Sheets")
            
            row_number_input = data.get('row_number')
            if row_number_input and int(row_number_input) > 0:
                row_number = int(row_number_input)
        else:
            status = "completado"
            
            row_number_input = data.get('row_number')
            
            if row_number_input and int(row_number_input) > 0:
                sheets_manager.update_consultation(
                    row_number=int(row_number_input),
                    user_query=user_message,
                    bot_response=response,
                    query_type=query_type,
                    status=status
                )
                row_number = int(row_number_input)
                print(f"[API] Fila {row_number} actualizada en Google Sheets")
            else:
                row_number = sheets_manager.log_consultation(
                    user_query=user_message,
                    bot_response=response,
                    query_type=query_type,
                    status=status
                )
                print(f"[API] Nueva fila {row_number} creada en Google Sheets")
        
        return jsonify({
            "success": True,
            "response": response,
            "query_type": query_type,
            "row_number": row_number
        })
        
    except Exception as e:
        print(f"[API] Error: {e}")
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Error interno del servidor",
            "details": str(e) if DEBUG_MODE else None
        }), 500


@app.route('/api/documents', methods=['GET'])
def list_documents():
    """Endpoint para listar los documentos disponibles."""
    try:
        if not is_authenticated():
            return jsonify({
                "success": False,
                "error": "not_authenticated"
            }), 401
        
        drive_manager = get_drive_manager()
        files = drive_manager.list_pdf_files()
        
        return jsonify({
            "success": True,
            "documents": [
                {"name": f['name'], "id": f['id']}
                for f in files
            ],
            "total": len(files)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache():
    """Fuerza la actualización del cache de documentos."""
    try:
        if not is_authenticated():
            return jsonify({
                "success": False,
                "error": "not_authenticated"
            }), 401
        
        drive_manager = get_drive_manager()
        drive_manager.refresh_cache()
        
        web_scraper = get_web_scraper()
        web_scraper.get_all_website_content(force_refresh=True)
        
        return jsonify({
            "success": True,
            "message": "Cache actualizado correctamente"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Endpoint para obtener estadísticas de consultas."""
    try:
        if not is_authenticated():
            return jsonify({
                "success": False,
                "error": "not_authenticated"
            }), 401
        
        sheets_manager = get_sheets_manager()
        stats = sheets_manager.get_statistics()
        
        return jsonify({
            "success": True,
            "statistics": stats
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Endpoint para registrar el feedback del usuario sobre una respuesta."""
    try:
        if not is_authenticated():
            return jsonify({
                "success": False,
                "error": "not_authenticated"
            }), 401
        
        data = request.json
    
        message_id = data.get('message_id', '')
        feedback_type = data.get('feedback_type', '')
        comment = data.get('comment', '')
        bot_response = data.get('bot_response', '')
        user_query = data.get('user_query', '')
        row_number = data.get('row_number', 0)
        
        if feedback_type not in ['like', 'dislike', 'none']:
            return jsonify({
                "success": False,
                "error": "Tipo de feedback inválido"
            }), 400
        
        print(f"\n[API] Feedback recibido: {feedback_type}")
        
        if feedback_type == 'none':
            comment = ""
        if comment:
            print(f"[API] Comentario: {comment[:100]}...")
        
        sheets_manager = get_sheets_manager()
        success = False
        
        if row_number and int(row_number) > 0:
            success = sheets_manager.update_feedback(
                row_number=int(row_number),
                feedback_type=feedback_type,
                comment=comment
            )
        else:
            success = sheets_manager.log_feedback(
                user_query=user_query,
                bot_response=bot_response,
                feedback_type=feedback_type,
                comment=comment,
                message_id=message_id
            )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Feedback registrado correctamente"
            })
        else:
            return jsonify({
                "success": False,
                "error": "No se pudo registrar el feedback"
            }), 500
        
    except Exception as e:
        print(f"[API] Error en feedback: {e}")
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Error interno del servidor"
        }), 500


# Punto de entrada
if __name__ == '__main__':
    print("=" * 60)
    print("  ASISTENTE VIRTUAL - IESTP JUAN VELASCO ALVARADO")
    print("=" * 60)
    print(f"\n[Servidor] Iniciando en http://localhost:{SERVER_PORT}")
    
    if is_authenticated():
        print("[Inicializando] Ya autenticado con Google")
        try:
            print("[Inicializando] Conectando con Google Drive...")
            drive_mgr = get_drive_manager()
            
            print("[Inicializando] Conectando con Google Sheets...")
            get_sheets_manager()
            
            print("[Inicializando] Configurando AI Manager...")
            get_ai_manager()
            
            print("[Inicializando] Configurando Web Scraper...")
            get_web_scraper()
            
            print("[Inicializando] Precargando documentos PDF...")
            drive_mgr.get_all_documents_text()
            
            print("\n[Servidor] Todas las conexiones establecidas")
        except Exception as e:
            print(f"\n[ADVERTENCIA] Error al inicializar: {e}")
    else:
        print("[Inicializando] No autenticado con Google")
        print(f"[Inicializando] Visita: http://localhost:{SERVER_PORT}/api/auth/url")
    
    print("[Servidor] Listo para recibir conexiones\n")
    
    app.run(
        host='0.0.0.0',
        port=SERVER_PORT,
        debug=DEBUG_MODE
    )
