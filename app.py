"""
Aplicación Flask Principal - ConectAI-JVA (V2 Optimizado)
---------------------------------------------------------
Autor: Exdly
Optimización: Integración Auth Robusta & Sincronización Híbrida (Supabase + Sheets)
"""

import os
import uuid
import datetime
import traceback
import json
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from dotenv import load_dotenv

# Google Auth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Módulos Internos
from config import (
    GOOGLE_CLIENT_ID, ALLOWED_ORIGINS, IS_VERCEL, DEBUG_MODE
)
from storage_manager import HybridStorageManager
from google_drive import GoogleDriveManager
from ai_manager import AIManager
from web_scraper import WebScraper
from smart_response import get_smart_response

# Cargar variables de entorno
load_dotenv()

# ==============================================================================
# CONFIGURACIÓN APP
# ==============================================================================

STATIC_FOLDER = 'static'
app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='/static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24)) # Necesario para sesiones

# Configuración CORS Robust
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=True)

# ==============================================================================
# GESTIÓN DE SINGLETONS (Recursos Compartidos)
# ==============================================================================

_managers = {}

def get_manager(key, factory):
    """Factory simple para lazy loading de managers."""
    # En Vercel (stateless) intentamos recrear conexiones si es necesario,
    # pero cacheamos en memoria para la duración de la instancia lambda.
    if key not in _managers:
        try:
            _managers[key] = factory()
        except Exception as e:
            print(f"[App] Error inicializando {key}: {e}")
            return None
    return _managers[key]

def get_sheets_manager(): 
    return get_manager('storage', lambda: HybridStorageManager())

def get_drive_manager():
    return get_manager('drive', lambda: GoogleDriveManager())

def get_ai_manager():
    return get_manager('ai', lambda: AIManager())

def get_web_scraper():
    return get_manager('scraper', lambda: WebScraper())

# ==============================================================================
# MIDDLEWARE & HELPERS
# ==============================================================================

@app.errorhandler(500)
def handle_500(e):
    traceback.print_exc()
    return jsonify({"success": False, "error": "Error interno del servidor", "details": str(e)}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"success": False, "error": "Recurso no encontrado"}), 404

def safe_execution(func):
    """Decorador para manejar excepciones en rutas API limpio."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"[API Error] {request.path}: {e}")
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500
    wrapper.__name__ = func.__name__
    return wrapper

# ==============================================================================
# RUTAS DE CONFIGURACIÓN
# ==============================================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Devuelve configuración pública para el frontend."""
    return jsonify({"google_client_id": GOOGLE_CLIENT_ID})

# ==============================================================================
# RUTAS DE AUTENTICACIÓN
# ==============================================================================

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Verifica si hay una sesión activa en el servidor."""
    if 'user' in session:
        return jsonify({"logged_in": True, "user": session['user']})
    return jsonify({"logged_in": False})

@app.route('/api/auth/login', methods=['POST'])
@safe_execution
def google_login():
    data = request.json
    token = data.get('credential')
    
    if not token:
        return jsonify({"success": False, "error": "No credential provided"}), 400
        
    try:
        # [FIX CRÍTICO] clock_skew_in_seconds=300 (5 min) tolera desincronización de hora
        id_info = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=300 
        )
        
        email = id_info['email']
        name = id_info.get('name', '')
        picture = id_info.get('picture', '')
        
        # Guardar en sesión
        user_data = {"email": email, "name": name, "picture": picture}
        session['user'] = user_data
        session.permanent = True # La sesión persiste al cerrar navegador si está configurado así
        
        # Sincronizar usuario con BD (no bloqueante)
        sheets_manager = get_sheets_manager()
        if sheets_manager:
            sheets_manager.create_or_update_user(email, name, picture)
        
        # Siempre retornar los datos del usuario
        return jsonify({
            "success": True, 
            "user": user_data
        })
              
    except ValueError as e:
        print(f"[Auth] Validación fallida (Clock Skew?): {e}")
        return jsonify({"success": False, "error": f"Token inválido: {str(e)}"}), 401

@app.route('/api/auth/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return jsonify({"success": True})

# ==============================================================================
# RUTAS DE CONVERSACIONES
# ==============================================================================

@app.route('/api/conversations', methods=['GET'])
@safe_execution
def get_conversations():
    """Obtiene el historial de conversaciones de un usuario."""
    email = request.args.get('email')
    if not email:
        return jsonify({"conversations": []})
    
    sheets_manager = get_sheets_manager()
    conversations = sheets_manager.get_user_conversations(email) if sheets_manager else []
    return jsonify({"conversations": conversations or []})

@app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
@safe_execution
def get_conversation_messages(conversation_id):
    """Obtiene los mensajes de una conversación específica."""
    sheets_manager = get_sheets_manager()
    messages = sheets_manager.get_conversation_messages(conversation_id) if sheets_manager else []
    return jsonify({"success": True, "messages": messages or []})

@app.route('/api/conversations/<cid>', methods=['DELETE', 'PUT'])
@safe_execution
def manage_conversation(cid):
    """Renombra o elimina conversación."""
    sm, data = get_sheets_manager(), request.get_json(silent=True) or {}
    if request.method == 'DELETE': return jsonify({"success": sm.delete_conversation(cid, request.args.get('email'))})
    return jsonify({"success": sm.update_conversation_title(cid, data.get('title'))})

# ==============================================================================
# RUTAS CORE DEL CHAT
# ==============================================================================

@app.route('/api/chat', methods=['POST'])
@safe_execution
def chat():
    """Endpoint principal de Chat. Maneja consultas, contexto y registro híbrido."""
    data = request.json
    user_message = data.get('message', '').strip()
    conversation_id = data.get('conversation_id')
    user_email = data.get('user_email')
    
    if not user_message:
        return jsonify({"success": False, "error": "Mensaje vacío"}), 400

    sheets_manager = get_sheets_manager()
    
    # 1. Gestión de Conversación
    if user_email and not conversation_id:
        # Nueva conversación
        title = (user_message[:30] + "...") if len(user_message) > 30 else user_message
        conversation_id = sheets_manager.create_conversation(user_email, title)
        print(f"[Chat] Nueva conversación: {conversation_id}")

    # 2. Guardar mensaje usuario (si hay conversación)
    # [IMPORTANTE] Guardamos el ID para retornarlo si fuera necesario, 
    # aunque log_consultation usa más el ID del bot para el logging principal.
    if conversation_id:
        if not sheets_manager.add_message(conversation_id, "user", user_message):
            # Fallback: Si falla (ej. conversación borrada), crear nueva
            if user_email: 
                conversation_id = sheets_manager.create_conversation(user_email, (user_message[:30] + "...") if len(user_message) > 30 else user_message)
                sheets_manager.add_message(conversation_id, "user", user_message)
            else: conversation_id = None # Anonimo sin conv valida

    # 3. Generación de Respuesta (Lógica desacoplada en chatbot_logic.py)
    #    Obtenemos managers frescos para asegurar contexto
    drive_manager = get_drive_manager()
    web_scraper = get_web_scraper()
    ai_manager = get_ai_manager()
    
    pdf_context = drive_manager.search_in_documents(user_message) if drive_manager else ""
    web_context = web_scraper.get_all_website_content() if web_scraper else ""
    
    # Función lambda para fallback de AI
    fallback_generator = lambda: ai_manager.generate_response(user_message, pdf_context, web_context) if ai_manager else "Error AI"

    response, source = get_smart_response(
        user_message=user_message,
        pdf_context=pdf_context,
        web_context=web_context,
        ai_fallback_func=fallback_generator
    )

    if not response:
        response = "Lo siento, no pude procesar tu solicitud en este momento."
        query_type = "error"
    else:
        # Determinar tipo query simple
        query_type = "general"
        lower_msg = user_message.lower()
        if "examen" in lower_msg or "admisión" in lower_msg: query_type = "admision"
        elif "matrícula" in lower_msg or "pago" in lower_msg: query_type = "matricula"
    
    # 4. Guardar mensaje Bot
    bot_msg_id = None
    if conversation_id:
        bot_msg_id = sheets_manager.add_message(conversation_id, "assistant", response)

    # 5. Registro Híbrido (Supabase 'consultas' + Google Sheets 'últimos 50')
    #    [CLAVE] Pasamos 'message_id' para vincular log y chat history
    log_id = sheets_manager.log_consultation(
        user_query=user_message,
        bot_response=response,
        query_type=query_type,
        status="completado",
        message_id=bot_msg_id
    )

    return jsonify({
        "success": True,
        "response": response,
        "conversation_id": conversation_id,
        "message_id": bot_msg_id,
        "log_id": log_id
    })

# ==============================================================================
# RUTAS DE GESTIÓN Y SINCRONIZACIÓN (EDITAR, REGENERAR, FEEDBACK)
# ==============================================================================

@app.route('/api/chat/message/<message_id>', methods=['PUT'])
@safe_execution
def update_message(message_id):
    """Edita un mensaje y sincroniza el cambio en los logs."""
    data = request.json
    new_content = data.get('content')
    original_content = data.get('original_content')  # Contenido original para buscar consulta
    
    if not new_content:
        return jsonify({"success": False, "error": "Contenido requerido"}), 400
        
    sheets_manager = get_sheets_manager()
    
    # 1. Actualizar Historial (Supabase 'messages')
    if message_id:
        sheets_manager.update_message(message_id, new_content)
        
    # 2. Sincronizar Log (Supabase 'consultas' + Sheets)
    # [OPTIMIZADO] Intentar actualizar por ID de mensaje primero (más preciso)
    updated = sheets_manager.update_consultation_by_message_id(
        message_id=message_id, 
        user_query=new_content
    )
    
    if not updated and original_content:
        # Fallback: Buscar consulta por contenido original y actualizarla
        sheets_manager.update_consultation_by_query(
            original_query=original_content,
            new_query=new_content
        )
    
    return jsonify({"success": True})

@app.route('/api/chat/regenerate', methods=['POST'])
@safe_execution
def regenerate_response():
    """Regenera la última respuesta del bot y actualiza historial + logs."""
    data = request.json
    conversation_id = data.get('conversation_id')
    
    if not conversation_id:
        return jsonify({"success": False, "error": "ID conversación requerido"}), 400
        
    sheets_manager = get_sheets_manager()
    messages = sheets_manager.get_conversation_messages(conversation_id)
    
    if not messages:
        return jsonify({"success": False, "error": "Conversación vacía"}), 404
        
    # Buscar el último par User-Bot para regenerar
    last_user_msg = None
    target_bot_msg_id = None
    
    # Recorrido inverso eficiente
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg['role'] == 'user':
            last_user_msg = msg
            break
        elif msg['role'] == 'assistant':
            # Queremos sobrescribir el último mensaje del bot si es el inmediatamente posterior?
            # O simplemente el último mensaje bot encontrado.
            # Asumiremos el último bot encontrado como target.
            if not target_bot_msg_id: target_bot_msg_id = msg['id']
            
    if not last_user_msg:
        return jsonify({"success": False, "error": "No hay mensaje de usuario previo"}), 400
        
    # Re-generar respuesta
    user_message = last_user_msg['content']
    
    # (Reutilizamos lógica de generación - idealmente en función helper pero por contexto...)
    drive_manager = get_drive_manager()
    web_scraper = get_web_scraper()
    ai_manager = get_ai_manager()
    
    pdf_context = drive_manager.search_in_documents(user_message) if drive_manager else ""
    web_context = web_scraper.get_all_website_content() if web_scraper else ""
    
    response, _ = get_smart_response(
        user_message=user_message,
        pdf_context=pdf_context,
        web_context=web_context,
        ai_fallback_func=lambda: ai_manager.generate_response(user_message, pdf_context, web_context)
    )

    if response:
        if target_bot_msg_id:
            # Sobrescribir mensaje existente en historial
            sheets_manager.update_message(target_bot_msg_id, response)
            # Sincronizar Log (intentar por message_id, si falla por contenido)
            if not sheets_manager.update_consultation_by_message_id(
                message_id=target_bot_msg_id,
                bot_response=response
            ):
                # Fallback: buscar por contenido original del usuario
                sheets_manager.update_consultation_by_query(
                    original_query=user_message,
                    new_response=response
                )
        else:
            # Crear nuevo si no había respuesta previa
            target_bot_msg_id = sheets_manager.add_message(conversation_id, "assistant", response)
            
        return jsonify({"success": True, "response": response, "message_id": target_bot_msg_id})
    else:
        return jsonify({"success": False, "error": "Fallo al generar respuesta"}), 500

@app.route('/api/chat/message/<message_id>/feedback', methods=['POST'])
@safe_execution
def feedback_endpoint(message_id):
    """Maneja Like/Dislike y sincroniza."""
    data = request.json
    feedback = data.get('feedback') # 'like', 'dislike', 'none'
    reason = data.get('reason', '')
    
    if feedback not in ['like', 'dislike', 'none']:
        return jsonify({"success": False, "error": "Tipo feedback inválido"}), 400
        
    sheets_manager = get_sheets_manager()
    
    # 1. Update Historial
    if sheets_manager.update_message_feedback(message_id, feedback, reason):
        # 2. Update Log Sincronizado
        sheets_manager.update_consultation_by_message_id(
            message_id=message_id,
            feedback=feedback,
            comment=reason
        )
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Mensaje no encontrado"}), 404

# ==============================================================================
# RUTAS DE DATOS (HISTORIAL, ETC)
# ==============================================================================

@app.route('/api/chat/history', methods=['GET'])
@safe_execution
def get_chat_history():
    email = request.args.get('email')
    if not email: return jsonify({"success": False, "error": "Email requerido"}), 400
    
    conversations = get_sheets_manager().get_user_conversations(email)
    return jsonify({"success": True, "conversations": conversations})

@app.route('/api/chat/conversation/<conversation_id>', methods=['GET'])
@safe_execution
def get_conversation_details(conversation_id):
    messages = get_sheets_manager().get_conversation_messages(conversation_id)
    return jsonify({"success": True, "messages": messages})

@app.route('/api/chat/conversation/<conversation_id>', methods=['DELETE'])
@safe_execution
def delete_conversation(conversation_id):
    # Implementación futura si requerida
    return jsonify({"success": True})

# ==============================================================================
# RUTAS ESTÁTICAS (FRONTEND)
# ==============================================================================

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Primero buscar en static
    static_path = os.path.join(STATIC_FOLDER, path)
    if os.path.exists(static_path):
        return send_from_directory(STATIC_FOLDER, path)
    # Fallback a templates/index.html para SPA
    return send_from_directory('templates', 'index.html')

# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG_MODE)
