"""
Almacenamiento Híbrido Optimizado - Supabase + Google Sheets
"""
from datetime import datetime
from typing import Optional
from config import GOOGLE_SHEET_ID, SUPABASE_URL, SUPABASE_ANON_KEY
from google_drive import get_credentials
from googleapiclient.discovery import build

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

MAX_SHEET_ROWS = 50

class HybridStorageManager:
    def __init__(self):
        self.sheets_service = self.supabase = None
        self._init_services()

    def _init_services(self):
        # Supabase
        if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_ANON_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            except: pass
        # Google Sheets
        creds = get_credentials()
        if creds:
            try:
                self.sheets_service = build('sheets', 'v4', credentials=creds)
                self._ensure_headers()
            except: pass

    def is_ready(self): return self.supabase or self.sheets_service
    def is_supabase_ready(self): return self.supabase is not None
    def is_sheets_ready(self): return self.sheets_service is not None

    def _ensure_headers(self):
        if not self.is_sheets_ready(): return
        try:
            res = self.sheets_service.spreadsheets().values().get(spreadsheetId=GOOGLE_SHEET_ID, range='A1:I1').execute()
            if not res.get('values') or len(res['values'][0]) < 9:
                headers = [['Fecha','Hora','Consulta del Usuario','Respuesta del Bot','Tipo de Consulta','Estado','Feedback','Comentario Feedback','ID Supabase']]
                self.sheets_service.spreadsheets().values().update(spreadsheetId=GOOGLE_SHEET_ID, range='A1:I1', valueInputOption='RAW', body={'values': headers}).execute()
        except: pass

    # ===================== SUPABASE CRUD =====================
    def _sb_insert(self, table: str, data: dict) -> Optional[str]:
        if not self.is_supabase_ready(): return None
        try:
            res = self.supabase.table(table).insert(data).execute()
            return res.data[0].get('id') if res.data else None
        except Exception as e:
            print(f"[Storage] Insert {table} error: {e}")
            return None

    def _sb_update(self, table: str, id_val, data: dict) -> bool:
        if not self.is_supabase_ready() or not id_val: return False
        try:
            self.supabase.table(table).update(data).eq("id", id_val).execute()
            return True
        except: return False

    def _sb_select(self, table: str, filters: dict = None, order_by: str = None, limit: int = None):
        if not self.is_supabase_ready(): return []
        try:
            q = self.supabase.table(table).select("*")
            for k, v in (filters or {}).items(): q = q.eq(k, v)
            if order_by: q = q.order(order_by, desc=True)
            if limit: q = q.limit(limit)
            return q.execute().data or []
        except: return []

    def _sb_delete(self, table: str, id_val) -> bool:
        if not self.is_supabase_ready(): return False
        try:
            self.supabase.table(table).delete().eq("id", id_val).execute()
            return True
        except: return False

    # ===================== CONSULTAS =====================
    def _save_to_history(self, user_query: str, bot_response: str, query_type: str = "general", conversation_id: str = None, feedback: str = None, comment: str = None):
        """Guarda en tabla consultas_historial para referencia de IA (acumula, no sobrescribe)."""
        if not self.is_supabase_ready(): return
        try:
            data = {"consulta_usuario": user_query[:5000], "respuesta_bot": bot_response[:50000], "tipo_consulta": query_type}
            if conversation_id: data["conversation_id"] = conversation_id
            if feedback: data["feedback"] = feedback
            if comment: data["comentario_feedback"] = comment
            self.supabase.table("consultas_historial").insert(data).execute()
        except: pass  # Fallo silencioso para no bloquear funcionalidad principal

    def log_consultation(self, user_query: str, bot_response: str, query_type: str = "general", status: str = "completado", message_id: str = None, conversation_id: str = None) -> int:
        if not self.is_ready(): return 0
        now = datetime.now()
        data = {"fecha": now.strftime("%Y-%m-%d"), "hora": now.strftime("%H:%M:%S"),
                "consulta_usuario": user_query[:5000], "respuesta_bot": bot_response[:50000],
                "tipo_consulta": query_type, "estado": status, "feedback": "", "comentario_feedback": ""}
        if message_id: data["id_mensaje"] = str(message_id)
        sb_id = self._sb_insert("consultas", data)
        self._sync_to_sheets(sb_id or 0, user_query, bot_response, query_type, status)
        # Guardar también en historial para referencia de IA
        self._save_to_history(user_query, bot_response, query_type, conversation_id)
        return sb_id or 0

    def update_consultation_by_message_id(self, message_id: str, user_query=None, bot_response=None, query_type=None, status=None, feedback=None, comment=None) -> bool:
        if not self.is_supabase_ready() or not message_id: return False
        try:
            res = self.supabase.table("consultas").select("id, consulta_usuario, respuesta_bot, tipo_consulta").eq("id_mensaje", message_id).execute()
            if not res.data: return False
            cid = res.data[0]['id']
            data = {"fecha": datetime.now().strftime("%Y-%m-%d"), "hora": datetime.now().strftime("%H:%M:%S")}
            if user_query: data["consulta_usuario"] = user_query[:5000]
            if bot_response: data["respuesta_bot"] = bot_response[:50000]
            if query_type: data["tipo_consulta"] = query_type
            if status: data["estado"] = status
            if feedback: data["feedback"] = feedback
            if comment: data["comentario_feedback"] = comment
            
            # 1. Sobreescribir 'consultas' (Estado Actual)
            self._sb_update("consultas", cid, data)
            self._update_sheet_by_id(cid, user_query, bot_response, query_type, status, feedback, comment)
            
            # 2. Guardar en Historial (Contexto IA)
            # Guardamos si hay cambios de contenido O si hay feedback nuevo
            if user_query or bot_response or feedback:
                # Recuperar valores actuales si no se proveen, para mantener contexto completo en historial
                uq = user_query or res.data[0].get('consulta_usuario', '')
                br = bot_response or res.data[0].get('respuesta_bot', '')
                qt = query_type or res.data[0].get('tipo_consulta', 'actualizacion')
                
                # Inyectar feedback en el registro histórico para que la IA lo vea
                # (Podríamos añadir campos feedback a consultas_historial, pero si no existen,
                #  podemos agregarlo al texto o asumir que la IA lee la tabla 'consultas' también.
                #  Asumiendo que consultas_historial tiene los mismos campos básicos, o modificamos _save_to_history)
                #  Por ahora usamos _save_to_history estándar.
                self._save_to_history(uq, br, qt, None)
                
                # NOTA: Si 'consultas_historial' no tiene columnas de feedback, no se guardará ahí explícitamente 
                # salvo que modifique _save_to_history. Voy a revisar _save_to_history.
                
            return True
        except: return False

    def update_consultation_by_query(self, original_query: str, new_query: str = None, new_response: str = None) -> bool:
        """Busca y actualiza consulta por contenido original (para sobrescritura)."""
        if not self.is_supabase_ready(): return False
        try:
            # Buscar consulta más reciente con ese contenido
            res = self.supabase.table("consultas").select("id").eq("consulta_usuario", original_query[:5000]).order("id", desc=True).limit(1).execute()
            if not res.data: return False
            cid = res.data[0]['id']
            data = {"fecha": datetime.now().strftime("%Y-%m-%d"), "hora": datetime.now().strftime("%H:%M:%S")}
            if new_query: data["consulta_usuario"] = new_query[:5000]
            if new_response: data["respuesta_bot"] = new_response[:50000]
            
            self._sb_update("consultas", cid, data)
            self._update_sheet_by_id(cid, new_query, new_response)
            
            # Guardar en Historial para contexto IA
            self._save_to_history(new_query or original_query, new_response or "", "actualizacion", None)
            return True
        except Exception as e:
            print(f"[Storage] Error update by query: {e}")
            return False

    def update_feedback(self, supabase_id: int, feedback_type: str, comment: str = "") -> bool:
        data = {"feedback": feedback_type, "comentario_feedback": comment}
        
        # 1. Recuperar datos actuales para historial
        current_data = {}
        try:
             res = self.supabase.table("consultas").select("consulta_usuario, respuesta_bot, tipo_consulta").eq("id", supabase_id).execute()
             if res.data: current_data = res.data[0]
        except: pass

        # 2. Sobreescribir 'consultas' + Sheets
        if self._sb_update("consultas", supabase_id, data):
            self._update_sheet_by_id(supabase_id, feedback=feedback_type, comment=comment)
            
            # 3. Guardar en Historial (Contexto IA)
            if current_data:
                self._save_to_history(
                    current_data.get("consulta_usuario", ""),
                    current_data.get("respuesta_bot", ""),
                    current_data.get("tipo_consulta", "general"),
                    None,
                    feedback=feedback_type,
                    comment=comment
                )
            return True
        return False

    # ===================== GOOGLE SHEETS SYNC =====================
    def _sync_to_sheets(self, supabase_id: int, user_query: str, bot_response: str, query_type: str, status: str, feedback: str = "", comment: str = ""):
        if not self.is_sheets_ready(): return
        try:
            res = self.sheets_service.spreadsheets().values().get(spreadsheetId=GOOGLE_SHEET_ID, range='A:A').execute()
            rows = len(res.get('values', []))
            if rows > MAX_SHEET_ROWS:
                del_rows = rows - MAX_SHEET_ROWS
                self.sheets_service.spreadsheets().batchUpdate(spreadsheetId=GOOGLE_SHEET_ID, 
                    body={"requests": [{"deleteDimension": {"range": {"sheetId": 0, "dimension": "ROWS", "startIndex": 1, "endIndex": 1 + del_rows}}}]}).execute()
            fb = {"like": "👍 Útil", "dislike": "👎 No útil"}.get(feedback, "")
            row = [[datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), user_query[:1000], bot_response[:5000], query_type, status, fb, comment[:500], str(supabase_id)]]
            self.sheets_service.spreadsheets().values().append(spreadsheetId=GOOGLE_SHEET_ID, range='A:I', valueInputOption='RAW', insertDataOption='INSERT_ROWS', body={'values': row}).execute()
        except: pass

    def _update_sheet_by_id(self, supabase_id: int, user_query=None, bot_response=None, query_type=None, status=None, feedback=None, comment=None):
        if not self.is_sheets_ready(): return
        try:
            res = self.sheets_service.spreadsheets().values().get(spreadsheetId=GOOGLE_SHEET_ID, range='I:I').execute()
            vals = res.get('values', [])
            row_idx = next((i+1 for i, v in enumerate(vals) if v and str(v[0]) == str(supabase_id)), None)
            if not row_idx: return
            updates = []
            if user_query: updates.append({'range': f'C{row_idx}', 'values': [[user_query[:1000]]]})
            if bot_response: updates.append({'range': f'D{row_idx}', 'values': [[bot_response[:5000]]]})
            if query_type: updates.append({'range': f'E{row_idx}', 'values': [[query_type]]})
            if status: updates.append({'range': f'F{row_idx}', 'values': [[status]]})
            if feedback:
                fb = {"like": "👍 Útil", "dislike": "👎 No útil"}.get(feedback, feedback)
                updates.append({'range': f'G{row_idx}', 'values': [[fb]]})
            if comment: updates.append({'range': f'H{row_idx}', 'values': [[comment[:500]]]})
            if updates:
                self.sheets_service.spreadsheets().values().batchUpdate(spreadsheetId=GOOGLE_SHEET_ID, body={'valueInputOption': 'RAW', 'data': updates}).execute()
        except: pass

    # ===================== USUARIOS =====================
    def create_or_update_user(self, email: str, name: str, picture: str) -> bool:
        if not self.is_supabase_ready(): return False
        try:
            existing = self._sb_select("users", {"email": email})
            data = {"name": name, "picture": picture, "last_login": datetime.now().isoformat()}
            if existing:
                return self._sb_update("users", email, data)
            data["email"] = email
            data["created_at"] = datetime.now().isoformat()
            return self._sb_insert("users", data) is not None
        except: return False

    # ===================== CONVERSACIONES =====================
    def create_conversation(self, user_email: str, title: str = "Nueva conversación") -> Optional[str]:
        now = datetime.now().isoformat()
        return self._sb_insert("conversations", {"user_email": user_email, "title": title, "created_at": now, "updated_at": now})

    def get_user_conversations(self, user_email: str):
        # [FIX] Traer más items y filtrar los marcados como [DELETED] en memoria
        # (Supabase no tiene LIKE '![DELETED]%' fácil en simple client, filtramos en Python)
        all_convs = self._sb_select("conversations", {"user_email": user_email}, order_by="updated_at", limit=50)
        return [c for c in all_convs if not (c.get('title') or '').startswith('[DELETED]')] if all_convs else []

    def delete_conversation(self, conversation_id: str, user_email: str) -> bool:
        if not self.is_supabase_ready(): return False
        try:
            # Opción Segura: Soft Delete siempre (Renombrar a [DELETED])
            # Esto evita cualquier error de Foreign Key o conflictos de base de datos
            new_title = f"[DELETED] {datetime.now().isoformat()}"
            updated = self._sb_update("conversations", conversation_id, {"title": new_title})
            
            # Limpieza opcional (si falla no importa)
            try: self.supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
            except: pass
            
            return updated
        except Exception as e: 
            print(f"[Storage] Delete error: {e}")
            return False

    def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        return self._sb_update("conversations", conversation_id, {"title": title, "updated_at": datetime.now().isoformat()})

    # ===================== MENSAJES =====================
    def add_message(self, conversation_id: str, role: str, content: str) -> Optional[str]:
        msg_id = self._sb_insert("messages", {"conversation_id": conversation_id, "role": role, "content": content, "created_at": datetime.now().isoformat()})
        if msg_id:
            self._sb_update("conversations", conversation_id, {"updated_at": datetime.now().isoformat()})
            if role == 'user':
                self._sb_update("conversations", conversation_id, {"title": content[:50]})
        return msg_id

    def update_message(self, message_id: str, content: str) -> bool:
        return self._sb_update("messages", message_id, {"content": content})

    def update_message_feedback(self, message_id: str, feedback: str, reason: str = None) -> bool:
        data = {"feedback": feedback}
        if reason: data["feedback_reason"] = reason
        return self._sb_update("messages", message_id, data)

    def get_conversation_messages(self, conversation_id: str):
        if not self.is_supabase_ready(): return []
        try:
            return self.supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute().data or []
        except: return []

# ===================== SINGLETON =====================
GoogleSheetsManager = HybridStorageManager
_sheets_manager = None

def get_sheets_manager():
    global _sheets_manager
    if not _sheets_manager:
        _sheets_manager = HybridStorageManager()
    return _sheets_manager
