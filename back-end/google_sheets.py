"""
Módulo de Almacenamiento Híbrido - Supabase + Google Sheets
============================================================
Este módulo maneja el registro de consultas usando:
- Supabase: Almacenamiento principal (todas las consultas)
- Google Sheets: Visualización de las últimas N consultas (no se sobrecarga)
"""

import os
from datetime import datetime
from typing import Optional
from googleapiclient.discovery import build

from config import GOOGLE_SHEET_ID, SUPABASE_URL, SUPABASE_ANON_KEY, SHEETS_MAX_ROWS

from google_drive import get_credentials, is_authenticated

# Import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("[Storage] ADVERTENCIA: Supabase no instalado. Ejecuta: pip install supabase")


class HybridStorageManager:
    """Clase para manejar el almacenamiento híbrido (Supabase + Google Sheets)."""
    
    def __init__(self):
        self.sheets_service = None
        self.supabase: Optional[Client] = None
        
        # Inicializar Supabase
        if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_ANON_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
                print("[Storage] Supabase conectado exitosamente")
            except Exception as e:
                print(f"[Storage] Error conectando a Supabase: {e}")
        
        # Inicializar Google Sheets (si hay credenciales)
        creds = get_credentials()
        if creds:
            try:
                self.sheets_service = build('sheets', 'v4', credentials=creds)
                self._ensure_headers()
                print("[Storage] Google Sheets conectado exitosamente")
            except Exception as e:
                print(f"[Storage] Error conectando a Google Sheets: {e}")
    
    def is_ready(self) -> bool:
        """Verifica si al menos un servicio está listo."""
        return self.supabase is not None or self.sheets_service is not None
    
    def is_supabase_ready(self) -> bool:
        """Verifica si Supabase está listo."""
        return self.supabase is not None
    
    def is_sheets_ready(self) -> bool:
        """Verifica si Google Sheets está listo."""
        return self.sheets_service is not None
    
    def reconnect(self):
        """Reconecta con nuevas credenciales."""
        creds = get_credentials()
        if creds:
            try:
                self.sheets_service = build('sheets', 'v4', credentials=creds)
                self._ensure_headers()
                print("[Storage] Google Sheets reconectado exitosamente")
                return True
            except Exception as e:
                print(f"[Storage] Error reconectando a Google Sheets: {e}")
        return False
    
    def _ensure_headers(self):
        """Asegura que Google Sheets tenga los encabezados correctos."""
        if not self.is_sheets_ready():
            return
        
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=GOOGLE_SHEET_ID,
                range='A1:I1'
            ).execute()
            
            values = result.get('values', [])
            
            if not values or len(values[0]) < 9:
                headers = [[
                    'Fecha',
                    'Hora',
                    'Consulta del Usuario',
                    'Respuesta del Bot',
                    'Tipo de Consulta',
                    'Estado',
                    'Feedback',
                    'Comentario Feedback',
                    'ID Supabase'  # Nuevo: referencia a Supabase
                ]]
                
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    range='A1:I1',
                    valueInputOption='RAW',
                    body={'values': headers}
                ).execute()
                
                print("[Storage] Encabezados de Google Sheets actualizados")
        except Exception as e:
            print(f"[Storage] Error al verificar encabezados: {e}")
    
    def _save_to_supabase(
        self,
        user_query: str,
        bot_response: str,
        query_type: str = "general",
        status: str = "completado",
        feedback: str = "",
        comment: str = ""
    ) -> Optional[int]:
        """Guarda una consulta en Supabase. Retorna el ID insertado."""
        if not self.is_supabase_ready():
            return None
        
        try:
            now = datetime.now()
            data = {
                "fecha": now.strftime("%Y-%m-%d"),
                "hora": now.strftime("%H:%M:%S"),
                "consulta_usuario": user_query[:5000],
                "respuesta_bot": bot_response[:50000],
                "tipo_consulta": query_type,
                "estado": status,
                "feedback": feedback,
                "comentario_feedback": comment
            }
            
            result = self.supabase.table("consultas").insert(data).execute()
            
            if result.data and len(result.data) > 0:
                supabase_id = result.data[0].get('id')
                print(f"[Storage] Supabase: Consulta guardada (ID: {supabase_id})")
                return supabase_id
            return None
            
        except Exception as e:
            print(f"[Storage] Error guardando en Supabase: {e}")
            return None
    
    def _update_supabase(
        self,
        supabase_id: int,
        user_query: str = None,
        bot_response: str = None,
        query_type: str = None,
        status: str = None,
        feedback: str = None,
        comment: str = None
    ) -> bool:
        """Actualiza una consulta existente en Supabase."""
        if not self.is_supabase_ready() or not supabase_id:
            return False
        
        try:
            now = datetime.now()
            data = {"fecha": now.strftime("%Y-%m-%d"), "hora": now.strftime("%H:%M:%S")}
            
            if user_query is not None:
                data["consulta_usuario"] = user_query[:5000]
            if bot_response is not None:
                data["respuesta_bot"] = bot_response[:50000]
            if query_type is not None:
                data["tipo_consulta"] = query_type
            if status is not None:
                data["estado"] = status
            if feedback is not None:
                data["feedback"] = feedback
            if comment is not None:
                data["comentario_feedback"] = comment
            
            self.supabase.table("consultas").update(data).eq("id", supabase_id).execute()
            print(f"[Storage] Supabase: Consulta actualizada (ID: {supabase_id})")
            return True
            
        except Exception as e:
            print(f"[Storage] Error actualizando Supabase: {e}")
            return False
    
    def _sync_to_sheets(
        self,
        supabase_id: int,
        user_query: str,
        bot_response: str,
        query_type: str,
        status: str,
        feedback: str = "",
        comment: str = ""
    ) -> int:
        """Sincroniza la consulta a Google Sheets (mantiene solo últimas N filas)."""
        if not self.is_sheets_ready():
            return 0
        
        try:
            now = datetime.now()
            
            # Primero, verificar cuántas filas hay
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=GOOGLE_SHEET_ID,
                range='A:A'
            ).execute()
            
            values = result.get('values', [])
            current_rows = len(values)
            
            # Si hay más de SHEETS_MAX_ROWS, eliminar filas antiguas
            if current_rows > SHEETS_MAX_ROWS:
                rows_to_delete = current_rows - SHEETS_MAX_ROWS
                # Eliminar filas desde la 2 (después del encabezado)
                requests = [{
                    "deleteDimension": {
                        "range": {
                            "sheetId": 0,
                            "dimension": "ROWS",
                            "startIndex": 1,  # Después del encabezado
                            "endIndex": 1 + rows_to_delete
                        }
                    }
                }]
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    body={"requests": requests}
                ).execute()
                print(f"[Storage] Sheets: Eliminadas {rows_to_delete} filas antiguas")
            
            # Agregar nueva fila
            feedback_display = ""
            if feedback == "like":
                feedback_display = "👍 Útil"
            elif feedback == "dislike":
                feedback_display = "👎 No útil"
            
            row = [[
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                user_query[:1000],
                bot_response[:5000],  # Limitamos más en Sheets
                query_type,
                status,
                feedback_display,
                comment[:500] if comment else "",
                str(supabase_id) if supabase_id else ""
            ]]
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=GOOGLE_SHEET_ID,
                range='A:I',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': row}
            ).execute()
            
            # Extraer número de fila
            updated_range = result.get('updates', {}).get('updatedRange', '')
            row_number = 0
            if updated_range:
                try:
                    import re
                    match = re.search(r'!A(\d+):', updated_range)
                    if match:
                        row_number = int(match.group(1))
                except:
                    pass
            
            print(f"[Storage] Sheets: Sincronizado en fila {row_number}")
            return row_number
            
        except Exception as e:
            print(f"[Storage] Error sincronizando a Sheets: {e}")
            return 0
    
    def log_consultation(
        self,
        user_query: str,
        bot_response: str,
        query_type: str = "general",
        status: str = "completado"
    ) -> int:
        """
        Registra una consulta (almacenamiento híbrido).
        Retorna el ID de Supabase (no el row_number de Sheets).
        """
        if not self.is_ready():
            print("[Storage] Ningún servicio disponible")
            return 0
        
        # 1. Guardar en Supabase (principal)
        supabase_id = self._save_to_supabase(
            user_query=user_query,
            bot_response=bot_response,
            query_type=query_type,
            status=status
        )
        
        # 2. Sincronizar a Google Sheets (visualización)
        self._sync_to_sheets(
            supabase_id=supabase_id or 0,
            user_query=user_query,
            bot_response=bot_response,
            query_type=query_type,
            status=status
        )
        
        return supabase_id or 0
    
    def update_consultation(
        self,
        row_number: int,  # Ahora es supabase_id
        user_query: str,
        bot_response: str,
        query_type: str = "general",
        status: str = "completado"
    ) -> bool:
        """Actualiza una consulta existente en Supabase."""
        if not self.is_supabase_ready() or row_number <= 0:
            return False
        
        return self._update_supabase(
            supabase_id=row_number,
            user_query=user_query,
            bot_response=bot_response,
            query_type=query_type,
            status=status
        )
    
    def update_feedback(
        self,
        row_number: int,  # Ahora es supabase_id
        feedback_type: str,
        comment: str = ""
    ) -> bool:
        """Actualiza el feedback en Supabase."""
        if not self.is_supabase_ready() or row_number <= 0:
            return False
        
        # Determinar el valor a guardar
        feedback_value = ""
        if feedback_type == "like":
            feedback_value = "👍 Útil"
        elif feedback_type == "dislike":
            feedback_value = "👎 No útil"
        
        return self._update_supabase(
            supabase_id=row_number,
            feedback=feedback_value,
            comment=comment
        )
    
    def log_feedback(
        self,
        user_query: str,
        bot_response: str,
        feedback_type: str,
        comment: str = "",
        message_id: str = ""
    ) -> bool:
        """Registra feedback como nueva entrada (fallback)."""
        if not self.is_ready():
            return False
        
        feedback_value = "👍 Útil" if feedback_type == "like" else "👎 No útil"
        
        supabase_id = self._save_to_supabase(
            user_query=user_query,
            bot_response=bot_response,
            query_type="feedback",
            status="registrado",
            feedback=feedback_value,
            comment=comment
        )
        
        return supabase_id is not None
    
    def get_statistics(self) -> dict:
        """Obtiene estadísticas de las consultas (desde Supabase)."""
        if not self.is_supabase_ready():
            return {"total": 0, "por_tipo": {}, "error": "Supabase no disponible"}
        
        try:
            # Contar total
            result = self.supabase.table("consultas").select("id", count="exact").execute()
            total = result.count if hasattr(result, 'count') else len(result.data)
            
            # Contar por tipo (simplificado)
            all_data = self.supabase.table("consultas").select("tipo_consulta").execute()
            tipo_count = {}
            for row in all_data.data:
                tipo = row.get('tipo_consulta', 'general')
                tipo_count[tipo] = tipo_count.get(tipo, 0) + 1
            
            return {
                "total": total,
                "por_tipo": tipo_count
            }
            
        except Exception as e:
            print(f"[Storage] Error obteniendo estadísticas: {e}")
            return {"total": 0, "por_tipo": {}, "error": str(e)}


# =============================================================================
# COMPATIBILIDAD: Mantener la interfaz anterior
# =============================================================================

# Alias para compatibilidad (GoogleSheetsManager ahora es HybridStorageManager)
GoogleSheetsManager = HybridStorageManager

# Instancia global (singleton)
_sheets_manager = None

def get_sheets_manager() -> HybridStorageManager:
    """Obtiene la instancia del manejador de almacenamiento híbrido."""
    global _sheets_manager
    if _sheets_manager is None:
        _sheets_manager = HybridStorageManager()
    return _sheets_manager
