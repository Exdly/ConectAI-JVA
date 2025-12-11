"""
Módulo Unificado de IA - IESTP Juan Velasco Alvarado
Versión: 7.0 [CONTEXTO CRUZADO + PERSISTENCIA SEGURA]
Optimización: Acepta 'smart_context' de Capas 1/2, Caché Tolerante a Fallos (Vercel) y Filtro Anti-PDF-Raw
"""

import re
import time
import json
import os
import requests
from typing import Optional, List, Dict
import google.generativeai as genai

from config import (
    OPENROUTER_API_KEY, GEMINI_API_KEY,
    OPENROUTER_MODELS, GEMINI_MODELS,
    AI_MAX_PDF_CONTEXT, AI_MAX_WEB_CONTEXT,
    CACHE_FOLDER
)

# Clasificaciones
QUERY_CLASSIFICATIONS = {
    'matrícula': ['matrícula', 'matricula', 'matricularme', 'inscripción', 'proceso', 'pasos'],
    'traslado': ['traslado', 'trasladar', 'cambiar de instituto'],
    'reserva': ['reserva', 'reservar'],
    'reincorporación': ['reincorporación', 'reincorporacion', 'volver'],
    'cambio_turno': ['cambio de turno', 'turno', 'horario'],
    'titulación': ['titulación', 'título', 'bachiller', 'titulado'],
    'costos': ['costo', 'precio', 'pago', 'cuánto', 'tarifa', 'mensualidad'],
    'fechas': ['fecha', 'plazo', 'cuándo', 'cronograma'],
    'requisitos': ['requisito', 'documento', 'necesito', 'papeles'],
    'vacantes': ['vacante', 'cupos', 'disponibilidad'],
    'carreras': ['carrera', 'programa', 'especialidad', 'arquitectura', 'contabilidad', 'enfermería', 'mecatrónica', 'farmacia'],
    'certificados': ['certificado', 'constancia', 'récord'],
    'becas': ['beca', 'becado', 'descuento', 'exoneración'],
    'saludo': ['hola', 'buenos días', 'buenas tardes', 'saludos'],
    'despedida': ['gracias', 'adiós', 'chau', 'hasta luego'],
}

class AIManager:
    """Gestor V7 con Contexto Cruzado y Persistencia Híbrida."""
    
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    CACHE_FILE = "cache/ai_response_cache.json"
    
    def __init__(self):
        self.openrouter_key = OPENROUTER_API_KEY
        self.openrouter_models = OPENROUTER_MODELS
        self.gemini_models = GEMINI_MODELS
        self.gemini_cooldowns: Dict[str, float] = {m: 0 for m in self.gemini_models}
        
        # CACHÉ DE RESPUESTAS (Intentar Carga Persistente)
        self.response_cache = self._load_cache_from_disk()
        self.max_cache_size = 1000
        
        print("\n" + "="*50)
        print("[AIManager V7] SISTEMA INICIADO (Contexto Cruzado Activado)")
        print(f"[AIManager] Respuestas en memoria: {len(self.response_cache)}")
        print("="*50 + "\n")
        
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
            except Exception as e:
                print(f"[AIManager] Error config Gemini: {e}")

    def _load_cache_from_disk(self) -> Dict[str, str]:
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[AIManager] Cache disco no legible (posiblemente entorno read-only o corrupto): {e}")
                return {}
        return {}

    def _save_cache_to_disk(self):
        """Intenta guardar en disco. Silencioso si falla (Vercel)."""
        try:
            os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.response_cache, f, ensure_ascii=False, indent=2)
            # print("[AIManager] 💾 Guardado.") # Comentado para no spammear logs
        except Exception:
            # En Vercel esto fallará a menudo. No importa, el caché vivirá en memoria del container activo.
            pass

    def _get_query_hash(self, text: str) -> str:
        clean = re.sub(r'[^\w\s]', '', text.lower()).strip()
        clean = re.sub(r'\s+', ' ', clean)
        return clean

    def _get_cached_response(self, query: str) -> Optional[str]:
        key = self._get_query_hash(query)
        if key in self.response_cache:
            print(f"[AIManager] ⚡ Cache HIT: '{key[:30]}...'")
            return self.response_cache[key]
        return None

    def _save_to_cache(self, query: str, response: str):
        key = self._get_query_hash(query)
        # LRU simple
        if len(self.response_cache) >= self.max_cache_size:
            first_key = next(iter(self.response_cache))
            del self.response_cache[first_key]
        self.response_cache[key] = response
        self._save_cache_to_disk()

    # DATOS VERIFICADOS V5 (Docentes Completos)
    VERIFIED_CONTEXT = {
        'costos': "INFORMACIÓN OFICIAL DE COSTOS (Fuente: TUPA 2025 VERIFICADA):\n- Matrícula Regular: S/. 200.00\n- Matrícula Extemporánea: S/. 260.00\n- Matrícula por Unidad Didáctica: S/. 50.00\n- Derecho de Examen de Admisión: S/. 200.00\n- Pagos en Banco de la Nación, Cta Cte: 0000289051.",
        'fechas': "CRONOGRAMA DE ADMISIÓN 2025 OFICIAL:\n- Inscripción Postulantes: 17 de febrero al 12 de abril 2025.\n- Inscripción Exonerados/Traslados: 14 de febrero al 14 de marzo 2025.\n- Examen de Admisión: Domingo 13 de abril 2025.\n- Inicio de Clases: 21 de abril 2025.",
        'becas': "INFORMACIÓN OFICIAL DE BECAS:\n- Beca de Excelencia: Exoneración del 100% de la matrícula para el primer puesto de cada semestre.\n- Beca Servicio Militar: Descuento del 50% en matrícula para licenciados o personal en servicio activo.",
        'matrícula': "PROCESO DE MATRÍCULA OFICIAL (TUPA 2025):\n1. REALIZAR PAGO: S/. 200.00 en Banco de la Nación (Cta 0000289051).\n2. CANJEAR VOUCHER: En Tesorería por Recibo de Ingreso.\n3. REGISTRO: En Secretaría Académica validar datos.\n4. FICHA DE MATRÍCULA: Recibir constancia firmada.",
        'autoridades': "AUTORIDADES VIGENTES 2025:\n- Directora General: Mg. Elsa Mary Castilla Almeyda\n- Jefe de Unidad Académica: Mg. Moisés Vargas Soto\n- Jefe de Administración: Lic. Cardenal Ipurre Contreras\n- Secretario Académico: Ing. Javier Alarcon Mayta",
        'ubicacion': "UBICACIÓN:\n- Dirección: Av. José Olaya N° 120, San Gabriel, Villa María del Triunfo.\n- Teléfonos: (01) 500 6177 / (01) 570 7726.\n"
    }

    def _inject_verified_context(self, query_type: str, user_message: str) -> str:
        injected_text = ""
        # 1. Inyección por tipo
        if query_type in self.VERIFIED_CONTEXT:
            injected_text += f"\n=== INFORMACIÓN OFICIAL VERIFICADA ({query_type.upper()}) ===\n{self.VERIFIED_CONTEXT[query_type]}\n"
        
        # 2. Inyección Carreras (Docentes Completos V5)
        query_norm = user_message.lower()
        career_data = {
            "farmacia": "DOCENTES TÉCNICA EN FARMACIA (8): Yolanda Suarez Diaz (Coord), Carmen Rosa Acco Gavilan, Seberino Alberto Canelo Blas, Miguel Ramiro Huarcaya Fernández, Fiorela Jeanette Ortiz Ortiz, Johao Junior Rodriguez Quishac, Emilia Ramirez Arnao, Shannon Calderon Quispe.",
            "enfermeria": "DOCENTES ENFERMERÍA TÉCNICA (8): Vicente Egusquiza Pozo (Coord), Fabiola Rodriguez Vega, Diana Noelia Saenz Charaja, Teresa Liliana Montoya Villasante, Leonor Nieto Pocomucha, Lizbeth Fabiola Jara Raraz, Sandra Oré Calderón, Mercedes Fuentes Lazo.",
            "arquitectura": "DOCENTES ARQUITECTURA (10): Hector Jorge Vidalón Jorge (Coord), Pedro Pachas Barrionuevo, Patricia Janet Benites Yglesias, Carlos Tasayco Yataco, Humberto Pablo Vega Cruz, John Harry Garriazo Castañeda, Christian Federico Flores Vargas, José Ricardo Cortez Camacho, Anthony Francisco Chuan Garcia, Luis Alberto Chacaltana Arnao.",
            "contabilidad": "DOCENTES CONTABILIDAD (9): Maria Cristina Maguiña Mallma (Coord), Elsa Castilla Almeyda, Teresa Cajo Rojas, Marisela Janet Palacios Castillo, Norma Yolanda Quispe Molina, Fernando Valderrama Castro, Luisa Verónica Sanchez Garcia, Elizabeth Manuela Ore Callirgos, Coralia Vilca Gonzales.",
            "mecatronica": "DOCENTES MECATRÓNICA (9): Cesar Augusto Curampa de la Cruz (Coord), Moisés Vargas Soto, Luis Agustín Mamani Chipana, Guillermo Carlos Barboza Tello, Jimmy Quispe Llamoca, Felix Hans Rivas Calla, Juan José Montaño Vega, Washington Ramirez Patiño, Juan Carlos Pancora Montes.",
            "empleabilidad": "DOCENTES EMPLEABILIDAD (10): Nilton Aquiles Michuy Suyo, Richard Mario Celis Calero, Daniel Quispe De La Torre, Juan Leopoldo Ranilla Medina, Wilmer Alarcon Mayta, Daniel Heli Flores Niño, Javier Alarcon Mayta, Lucia Lila Mendoza Huertas, Miguel Valerio Millones Yauri, Marilu Carpio Perez."
        }
        
        if query_type == 'carreras' or any(x in query_norm for x in ['docente', 'profesor', 'enseña']):
            for career, data in career_data.items():
                if career in query_norm:
                    injected_text += f"\n=== DATOS VERIFICADOS ({career.upper()}) ===\n{data}\n"
            if 'empleabilidad' in query_norm or 'transversal' in query_norm:
                 injected_text += f"\n=== DATOS VERIFICADOS (EMPLEABILIDAD) ===\n{career_data['empleabilidad']}\n"
                    
        return injected_text

    def _is_useful_response(self, response: str, query_type: str) -> bool:
        if not response or len(response) < 40: return False
        low = response.lower()
        
        # FILTRO ANTI-PDF-RAW (Lo que molestó al usuario)
        # Rechaza respuestas que parecen dumps de logs o encabezados de documentos sin explicación
        bad_patterns = [
            "--- página", "manual de procesos de régimen", "resolución directoral", 
            "fecha: 10 -07-2021", "código: mpa"
        ]
        if any(p in low for p in bad_patterns) and len(response) < 300:
             # Si es corto y tiene estos patrones, es basura. Si es largo, quizás explicó después.
             print("[AIManager] 🗑️ Rechazada respuesta tipo 'PDF Raw'")
             return False

        useless_phrases = ["no tengo información", "no encuentro", "contacta a la secretaría"]
        if any(p in low for p in useless_phrases):
            # Solo salvamos si tiene datos útiles
            if any(i in low for i in ["correo", "teléfono", "s/.", "1.", "•"]): return True
            return False
            
        return True

    def classify_query(self, message: str) -> str:
        text = message.lower().strip()
        replacements = {"á":"a", "é":"e", "í":"i", "ó":"o", "ú":"u", "ñ":"n"}
        for old, new in replacements.items(): text = text.replace(old, new)
        for qtype, keywords in QUERY_CLASSIFICATIONS.items():
            for kw in keywords:
                if kw in text: return qtype
        return 'general'

    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL V7: Acepta 'smart_context_injection'
    # -------------------------------------------------------------------------
    def generate_response(self, user_message: str, pdf_context: str, web_context: str = "", 
                         conversation_history: list = None, smart_context_injection: str = None) -> Optional[str]:
        """Genera respuesta usando todas las capas + Contexto Inyectado."""
        
        # 0. Cache Hit?
        cached = self._get_cached_response(user_message)
        if cached: return cached

        query_type = self.classify_query(user_message)
        
        # 1. Preparar Contexto Base
        gemini_context = self._get_relevant_context(user_message, pdf_context, max_chars=AI_MAX_PDF_CONTEXT)
        
        # 2. INYECCIÓN CRUZADA (Prioridad Máxima): ¿SmartResponse nos dio algo?
        if smart_context_injection:
            print(f"[AIManager] 🔗 Contexto Cruzado Recibido (Capa 1/2): {len(smart_context_injection)} chars")
            # Lo ponemos UN POCO ANTES de los datos verificados para que la IA entienda que es referencia
            gemini_context = f"=== CONTEXTO DE BÚSQUEDA PREVIO ===\n{smart_context_injection}\n\n" + gemini_context

        # 3. INYECCIÓN VERIFICADA (Datos Duros V5)
        verified_data = self._inject_verified_context(query_type, user_message)
        if verified_data:
            gemini_context = verified_data + "\n\n" + gemini_context
            
        final_web = self._get_relevant_context(user_message, web_context, max_chars=AI_MAX_WEB_CONTEXT)
        
        # 4. Invocación IA
        final_response = self._run_model_chain("gemini", user_message, gemini_context, final_web, conversation_history, query_type)
        
        if not final_response:
             # Fallback ligero
             final_response = self._run_model_chain("openrouter", user_message, gemini_context[:8000], final_web, conversation_history, query_type)

        # 5. Aprendizaje Automático
        if final_response:
             self._save_to_cache(user_message, final_response)
             
        return final_response

    def _get_relevant_context(self, query: str, full_context: str, max_chars: int = 40000) -> str:
        if len(full_context) < max_chars: return full_context
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        if not query_words: return full_context[:max_chars]
        
        chunks = full_context.split('\n\n')
        scored_chunks = []
        for chunk in chunks:
            if len(chunk) < 50: continue
            score = sum(chunk.lower().count(w) for w in query_words)
            scored_chunks.append((score, chunk))
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        selected = []
        cur = 0
        for sc, ch in scored_chunks:
            if cur + len(ch) > max_chars: break
            selected.append(ch)
            cur += len(ch)
        return "\n\n...\n\n".join(selected)

    def _run_model_chain(self, provider, user, pdf, web, hist, qtype):
        models = self.openrouter_models if provider == "openrouter" else self.gemini_models
        for m in models:
            resp = None
            if provider == "openrouter": resp = self._call_openrouter(m, user, pdf, web, hist)
            else: 
                if time.time() < self.gemini_cooldowns.get(m, 0): continue
                resp = self._call_gemini(m, user, pdf, web, hist)
            
            if resp and self._is_useful_response(resp, qtype): return resp
        return None

    def _build_prompt(self, user, pdf, web, hist):
        return f"""
=== ERES ===
Asistente Virtual IESTP Juan Velasco Alvarado.
=== FUENTES ===
{pdf[:25000]}
=== WEB ===
{web[:8000]}
=== HISTORIAL ===
{hist[-2:] if hist else ""}
=== PREGUNTA ===
{user}
=== INSTRUCCIÓN ===
Responde de forma ÚTIL, CLARA y AMABLE.
Si hay "CONTEXTO DE BÚSQUEDA PREVIO", úsalo para explicar el tema.
Si piden pasos, usa lista numerada.
NO devuelvas texto crudo del manual ("Página 7..."). REDACTA la respuesta.
"""

    def _call_gemini(self, model_name, user, pdf, web, hist):
        try:
            model = genai.GenerativeModel(model_name)
            prompt = self._build_prompt(user, pdf, web, hist)
            resp = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.4))
            return resp.text
        except Exception as e:
            self.gemini_cooldowns[model_name] = time.time() + 20
            return None

    def _call_openrouter(self, model, user, pdf, web, hist):
        try:
             headers = {"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"}
             data = {"model": model, "messages": [{"role":"user", "content": self._build_prompt(user, pdf, web, hist)}]}
             resp = requests.post(self.OPENROUTER_URL, headers=headers, json=data, timeout=30)
             if resp.status_code==200: return resp.json()['choices'][0]['message']['content']
        except: pass
        return None

_ai_manager = None
def get_ai_manager() -> AIManager:
    global _ai_manager
    if _ai_manager is None: _ai_manager = AIManager()
    return _ai_manager
