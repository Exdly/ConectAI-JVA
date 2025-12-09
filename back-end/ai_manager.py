"""
Módulo Unificado de IA - IESTP Juan Velasco Alvarado
=====================================================
Combina OpenRouter y Google Gemini en un solo gestor con fallback automático.
Estrategia: OpenRouter (Rápido/Barato) -> Gemini (Contexto Masivo/Razonamiento)
"""

import re
import time
import requests
from typing import Optional, List, Dict
import google.generativeai as genai

from config import (
    OPENROUTER_API_KEY, GEMINI_API_KEY,
    OPENROUTER_MODELS, GEMINI_MODELS,
    MODEL_TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT
)

# Clasificaciones de consultas
QUERY_CLASSIFICATIONS = {
    'matrícula': ['matrícula', 'matricula', 'matricularme', 'inscripción'],
    'traslado': ['traslado', 'trasladar', 'cambiar de instituto'],
    'reserva': ['reserva', 'reservar'],
    'reincorporación': ['reincorporación', 'reincorporacion', 'volver'],
    'cambio_turno': ['cambio de turno', 'turno', 'horario'],
    'titulación': ['titulación', 'título', 'bachiller', 'titulado'],
    'costos': ['costo', 'precio', 'pago', 'cuánto', 'tarifa'],
    'fechas': ['fecha', 'plazo', 'cuándo', 'cronograma'],
    'requisitos': ['requisito', 'documento', 'necesito'],
    'vacantes': ['vacante', 'cupos', 'disponibilidad'],
    'carreras': ['carrera', 'programa', 'especialidad'],
    'certificados': ['certificado', 'constancia', 'récord'],
    'becas': ['beca', 'becado', 'descuento', 'exoneración'],
    'saludo': ['hola', 'buenos días', 'buenas tardes', 'saludos'],
    'despedida': ['gracias', 'adiós', 'chau', 'hasta luego'],
}

class AIManager:
    """Gestor unificado de IA con selección inteligente y manejo robusto de rate limits."""
    
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    # Cooldown máximo (normalmente se usa el tiempo sugerido por la API)
    
    def __init__(self):
        self.openrouter_key = OPENROUTER_API_KEY
        self.openrouter_models = OPENROUTER_MODELS
        self.gemini_models = GEMINI_MODELS
        self.gemini_models = GEMINI_MODELS
        # Cooldown independiente por modelo
        self.gemini_cooldowns: Dict[str, float] = {m: 0 for m in self.gemini_models}
        
        # Diagnóstico de API Keys
        print("\n" + "="*50)
        print("[AIManager] DIAGNÓSTICO DE API KEYS")
        print("="*50)
        if OPENROUTER_API_KEY:
            print(f"[AIManager] OpenRouter API Key: OK (termina en ...{OPENROUTER_API_KEY[-4:]})")
        else:
            print("[AIManager] OpenRouter API Key: NO CONFIGURADA")
        
        if GEMINI_API_KEY:
            print(f"[AIManager] Gemini API Key: OK (termina en ...{GEMINI_API_KEY[-4:]})")
        else:
            print("[AIManager] Gemini API Key: NO CONFIGURADA")
        print("="*50 + "\n")
        
        # Configurar Gemini globalmente
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                print(f"[AIManager] Gemini configurado correctamente")
                
                # Test con el primer modelo disponible
                try:
                    test_model_name = self.gemini_models[0]
                    test_model = genai.GenerativeModel(test_model_name)
                    test_response = test_model.generate_content("Di solo 'OK' sin nada mas")
                    print(f"[AIManager] TEST Gemini ({test_model_name}): EXITOSO")
                except Exception as test_error:
                    print(f"[AIManager] TEST Gemini FALLÓ: {str(test_error)[:200]}")
            except Exception as e:
                print(f"[AIManager] Error configurando Gemini: {e}")
        else:
            print("[AIManager] ADVERTENCIA: GEMINI_API_KEY no esta definida.")
    
    def _can_call_gemini(self, model_name: str) -> bool:
        """Verifica si podemos llamar a un modelo específico de Gemini."""
        if not GEMINI_API_KEY: return False
        
        now = time.time()
        cooldown = self.gemini_cooldowns.get(model_name, 0)
        
        if now < cooldown:
            print(f"[AIManager] {model_name} en cooldown por {int(cooldown - now)}s")
            return False
        return True
    
    def _handle_gemini_error(self, error):
        """Maneja errores de Gemini, parseando el tiempo de espera sugerido por la API."""
        error_str = str(error)
        print(f"[AIManager] Error Gemini COMPLETO: {error_str[:500]}")  # Log completo
        
        if "429" in error_str or "Resource exhausted" in error_str:
            # Intentar parsear el tiempo de espera sugerido por Gemini
            retry_match = re.search(r'retry in (\d+\.?\d*)s', error_str)
            backoff = 20 # Default
            
            if retry_match:
                suggested_wait = float(retry_match.group(1))
                backoff = min(suggested_wait + 5, 60)  # Máximo 60s
                print(f"[AIManager] Gemini sugiere esperar {suggested_wait:.1f}s, usamos {backoff:.1f}s")
            else:
                print(f"[AIManager] Gemini 429 sin tiempo sugerido, usando {backoff}s")
            
            return backoff
            
        elif "404" in error_str or "not found" in error_str.lower():
             print(f"[AIManager] Modelo no encontrado (404) - Probando siguiente")
             return 0
        
        print(f"[AIManager] Error Gemini desconocido: {error_str[:100]}")
        return 5 # Error genérico, espera corta

    def _is_useful_response(self, response: str, query_type: str) -> bool:
        """Determina si una respuesta es útil basándose en el tipo de consulta."""
        if not response or len(response) < 50:
            return False
            
        low = response.lower()
        
        # 1. Chequeo de frases de "no sé" (rechazo inmediato)
        useless_phrases = [
            "no tengo información", "no encuentro información", 
            "no se menciona en los documentos", "lo siento", 
            "no puedo responder", "no hay documentos",
            "contacta a la secretaría", 
            "no está especificado", "no se proporciona", "no se encuentra",
            "no aparece en el texto", "no se detalla", "no cuento con la información",
            "no se indica", "no se menciona", "no dispongo de información"
        ]
        
        if any(p in low for p in useless_phrases):
            # SOLO salvamos la respuesta si da un contacto específico
            if "correo" in low or "teléfono" in low or "presencialmente" in low or "dirección" in low:
                return True
            print(f"[AIManager] Rechazada por frases negativas: {response[:100]}...")
            return False

        # 2. Chequeo estricto por TIPO de consulta
        if query_type in ['costos', 'matrícula', 'titulación']:
            # Si pregunta por costos/pagos, buscamos indicadores de dinero
            if 'costo' in low or 'pago' in low or 'precio' in low:
                if not re.search(r's/\.|soles|\d+(\.\d+)?', low):
                    print(f"[AIManager] Rechazada: Se pidieron costos pero no hay cifras.")
                    return False
                
        # Si el usuario pide fechas, debe haber números o meses
        if query_type in ['fechas', 'cronograma']:
            months = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
            if not (re.search(r'\d{1,2}', low) or any(m in low for m in months)):
                print(f"[AIManager] Rechazada: Se pidieron fechas pero no hay datos temporales.")
                return False

        return True

    def classify_query(self, message: str) -> str:
        msg_lower = message.lower()
        for qtype, keywords in QUERY_CLASSIFICATIONS.items():
            if any(kw in msg_lower for kw in keywords):
                return qtype
        return 'general'

    def generate_response(self, user_message: str, pdf_context: str, web_context: str = "", 
                         conversation_history: list = None) -> Optional[str]:
        """Genera respuesta intentando cadenas de modelos."""
        
        query_type = self.classify_query(user_message)
        print(f"[AIManager] Tipo de consulta: {query_type}")
        
        # 1. INTENTO CON OPENROUTER (Contexto limitado)
        # -----------------------------------------------------
        print("[AIManager] Iniciando cadena OpenRouter...")
        # Limitamos el contexto a ~30k caracteres (~8k tokens) para modelos con ventana pequeña
        # Esto evita errores HTTP 400 por contexto demasiado largo
        context_limited = pdf_context[:30000]
        print(f"[AIManager] Contexto limitado para OpenRouter: {len(context_limited)} chars")
        
        or_response = self._run_model_chain("openrouter", user_message, context_limited, web_context, conversation_history, query_type)
        
        if or_response and self._is_useful_response(or_response, query_type):
            print("[AIManager] [OK] Respuesta util encontrada en OpenRouter. Omitiendo Gemini.")
            return or_response
            
        print("[AIManager] OpenRouter no dio respuesta util. Probando Gemini...")
        
        # 2. INTENTO CON GEMINI (Contexto LIMITADO por cuota de tokens)
        # -----------------------------------------------------
        if True: # Siempre intentamos Gemini si OpenRouter falla
            # PREPARACIÓN DE CONTEXTO OPTIMIZADO (Smart Context)
            # Reducimos de 600k a 40k caracteres buscando lo relevante
            gemini_context = self._get_relevant_context(user_message, pdf_context, max_chars=40000)
            
            # 10k contexto web extra si cabe
            final_web = web_context[:10000]
            
            print(f"[AIManager] Contexto optimizado: {len(gemini_context)} chars (PDF) + {len(final_web)} chars (Web)")
            
            gm_response = self._run_model_chain("gemini", user_message, gemini_context, final_web, conversation_history, query_type)
            if gm_response:
                return gm_response
        
        return or_response

    def _get_relevant_context(self, query: str, full_context: str, max_chars: int = 40000) -> str:
        """Selecciona las partes más relevantes del texto para la consulta (filtro de tokens)."""
        if len(full_context) < max_chars:
            return full_context
            
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        if not query_words:
            return full_context[:max_chars] # Si no hay keywords claras, devolvemos el inicio
            
        # Dividir por secciones lógicas (ej. encabezados o párrafos dobles)
        chunks = full_context.split('\n\n')
        scored_chunks = []
        
        for chunk in chunks:
            if len(chunk) < 50: continue
            score = 0
            chunk_lower = chunk.lower()
            for word in query_words:
                score += chunk_lower.count(word)
            scored_chunks.append((score, chunk))
            
        # Ordenar por relevancia
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Seleccionar top chunks hasta llenar cupo
        selected = []
        current_len = 0
        for score, chunk in scored_chunks:
            if current_len + len(chunk) > max_chars:
                break
            selected.append(chunk)
            current_len += len(chunk)
            
        # IMPORTANTE: Reordenar chunks seleccionados para mantener coherencia si es posible
        # (Aunque aquí perdemos el orden original, para RAG simple suele bastar)
        print(f"[SmartContext] Seleccionados {len(selected)} bloques relevantes para '{query_words}'")
        return "\n\n...\n\n".join(selected)

    def _run_model_chain(self, provider: str, user_message: str, pdf_context: str, web_context: str, history: list, query_type: str) -> Optional[str]:
        """Ejecuta una cadena de modelos secuencialmente."""
        
        models = self.openrouter_models if provider == "openrouter" else self.gemini_models
        
        last_valid_response = None
        last_valid_provider = None
        
        for model_name in models:
            print(f"[AIManager] Intentando {provider.upper()}: {model_name}")
            
            response = None
            if provider == "openrouter":
                response = self._call_openrouter(model_name, user_message, pdf_context, web_context, history)
            else:
                # Verificar cooldown específico del modelo
                if not self._can_call_gemini(model_name):
                    continue # Saltar este modelo, probar siguiente INMEDIATAMENTE
                    
                response = self._call_gemini(model_name, user_message, pdf_context, web_context, history)
                
                # Gestión de errores específicos dentro de _call_gemini devuelve None
                # Si hubo error 429, el cooldown ya se seteó adentro de _call_gemini (necesitamos pasar self)
                pass
                
                
            if response:
                # Guardamos esta respuesta como "posible fallback" por si las siguientes fallan
                last_valid_response = response
                last_valid_provider = model_name
                
                if self._is_useful_response(response, query_type):
                    print(f"[AIManager] EXITO: {model_name} genero respuesta util ({len(response)} chars)")
                    return response
                else:
                    print(f"[AIManager] {model_name} genero respuesta NO util. Probando siguiente...")
            else:
                # Si falló (None), no tenemos nada que guardar
                print(f"[AIManager] {model_name} fallo. Probando siguiente...")
        
        # FINAL FALLBACK LOGIC
        # Si encontramos una respuesta útil, ya se retornó arriba.
        # Si llegamos aquí, ninguna fue "útil" según _is_useful_response.
        # PERO, si alguna generó texto (last_valid_response), devolvemos esa en lugar de None.
        if last_valid_response:
            print(f"[AIManager] Fallback Final: Devolviendo la mejor respuesta disponible de {last_valid_provider} ({len(last_valid_response)} chars)")
            return last_valid_response
            
        print("[AIManager] CRÍTICO: Ningún modelo generó respuesta válida.")
        return None

    def _build_prompt(self, user_message: str, pdf_context: str, web_context: str, history: list) -> str:
        return f"""
=== ROL ===
Eres el Asistente Virtual Oficial del IESTP Juan Velasco Alvarado.

=== MISIÓN ===
Tu ÚNICO objetivo es extraer y presentar DATOS EXACTOS (fechas, costos, requisitos) de los documentos proporcionados.

=== REGLAS DE ORO ===
1. **BUSCA EXHAUSTIVAMENTE**: La información ESTÁ en el texto. Busca precios en tablas, listas o anexos.
2. **NO SEAS GENÉRICO**: No digas "el costo varía". Di "El costo es S/. 450.00" (si está en el texto).
3. **SI ENCUENTRAS EL DATO**: Preséntalo directamente con viñetas.
4. **SI NO ENCUENTRAS EL DATO**: Di "No encuentro esa información específica en los documentos".

=== CONTEXTO (DOCUMENTOS Y WEB) ===
{pdf_context}
{web_context[:10000]}

=== HISTORIAL ===
{history[-2:] if history else "Inicio"}

=== CONSULTA ===
{user_message}
"""

    def _call_openrouter(self, model: str, user_message: str, pdf_context: str, web_context: str, history: list) -> Optional[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://iestpjva.edu.pe",
                "X-Title": "Asistente JVA"
            }
            
            messages = [{"role": "user", "content": self._build_prompt(user_message, pdf_context, web_context, history)}]
            
            resp = requests.post(
                self.OPENROUTER_URL,
                headers=headers,
                json={"model": model, "messages": messages, "temperature": 0.5, "max_tokens": 2000},
                timeout=45
            )
            
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content']
            else:
                print(f"[AIManager] OpenRouter {model} HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"[AIManager] Error OpenRouter {model}: {e}")
            return None

    def _call_gemini(self, model_name: str, user_message: str, pdf_context: str, web_context: str, history: list) -> Optional[str]:
        try:
            model = genai.GenerativeModel(model_name)
            prompt = self._build_prompt(user_message, pdf_context, web_context, history)
            
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.5, max_output_tokens=2000)
            )
            
            if hasattr(resp, 'text'): return resp.text
            if hasattr(resp, 'parts'): return "".join([p.text for p in resp.parts])
            return None
        except Exception as e:
            backoff = self._handle_gemini_error(e)
            if backoff > 0:
                self.gemini_cooldowns[model_name] = time.time() + backoff
                print(f"[AIManager] {model_name} pausado por {backoff}s. Probando siguiente...")
            return None

# Singleton
_ai_manager = None
def get_ai_manager() -> AIManager:
    global _ai_manager
    if _ai_manager is None: _ai_manager = AIManager()
    return _ai_manager
