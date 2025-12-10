"""
Sistema de Respuestas Inteligentes - IESTP Juan Velasco Alvarado
Versión: 7.1 [RESTORED CONTEXTUAL MAP + SMART ROUTING]
Corrección: Reintegración de 'universal_map' para garantizar respuestas FAQ limpias en consultas simples,
mientras se mantiene la capacidad V7 de explicar procesos complejos con IA.
"""

import time
from difflib import SequenceMatcher
from functools import lru_cache
from ai_manager import get_ai_manager

# ============================================================================
# 1. BASE DE CONOCIMIENTO (FAQ)
# ============================================================================

FAQ = {
    # Proceso de Matrícula (Redactado)
    "proceso matricula": ("Manual de Proceso de Matrícula (Paso a Paso):\n\n"
                          "1. REALIZAR PAGO: S/. 200.00 en Banco de la Nación (Cta. 0000289051) o Agentes Multired.\n"
                          "2. CANJEAR VOUCHER: Acercarse a Tesorería del Instituto para canjear el voucher por el Recibo de Ingreso.\n"
                          "3. REGISTRO ACADÉMICO: Ir a Secretaría Académica con el Recibo y DNI para validar datos.\n"
                          "4. FICHA DE MATRÍCULA: Recibir y firmar la Ficha de Matrícula generada por el sistema.\n"
                          "5. CONFIRMACIÓN: Se te entregará tu constancia de matriculado y horario de clases."),

    "cuanto cuesta matricula": ("Costos de Matrícula 2025 (Fuente TUPA):\n\n"
                                "• Matrícula Regular: S/. 200.00\n"
                                "• Matrícula Extemporánea: S/. 260.00\n"
                                "• Matrícula por Unidad Didáctica: S/. 50.00\n"
                                "• Banco: Banco de la Nación (Cta. 0000289051)"),
    
    "cuando examen admision": ("Cronograma de Admisión 2025:\n\n"
                               "• Inscripción Ordinaria: 17 Febrero - 12 Abril 2025\n"
                               "• Examen de Admisión: 13 Abril 2025\n"
                               "• Publicación Resultados: 19 Marzo 2025 (Exonerados) / 13 Abril (Ordinario)\n"
                               "• Inicio de Clases: Abril 2025"),
    
    "requisitos admision": ("Requisitos de Admisión:\n\n"
                            "1. Partida de Nacimiento (original o copia legalizada)\n"
                            "2. Certificado de Estudios Secundaria (original)\n"
                            "3. Copia de DNI\n"
                            "4. Voucher de pago por derecho de inscripción (S/. 200.00)\n"
                            "5. Carpeta de postulante (adquirir en Tesorería)"),

    # --- INSTITUCIONAL ---
    "mision vision": ("Misión y Visión Institucional:\n\n"
                      "🏆 VISIÓN (al 2026): Ser una institución licenciada y acreditada, líder en formación técnica con valores e innovación.\n\n"
                      "🎯 MISIÓN: Formar profesionales técnicos competentes, éticos y comprometidos con el medio ambiente y el mercado laboral."),
    
    "valores institucionales": ("Valores del IESTP JVA:\n\n"
                                "🤝 Solidaridad\n🏫 Identidad\n👥 Trabajo en equipo\n⏰ Puntualidad\n🙏 Respeto\n⚖️ Justicia\n💎 Honestidad"),

    "quienes autoridades": ("Autoridades (Plana Directiva):\n\n"
                            "• Dir. General: Mg. Elsa Mary Castilla Almeyda\n"
                            "• J. Unidad Académica: Mg. Moises Vargas Soto\n"
                            "• J. Administración: Lic. Cardenal Ipurre Contreras\n"
                            "• Secretario Académico: Ing. Javier Alarcon Mayta\n"
                            "• J. Bienestar: Patricia Janet Benites Yglesias"),

    "donde esta instituto": ("Ubicación Sede Principal:\n\n"
                             "📍 Av. José Olaya N° 120, San Gabriel - Villa María del Triunfo, Lima\n"
                             "📞 (01) 500 6177\n"
                             "✉️ secretaria.academica@iestpjva.edu.pe\n"
                             "Horarios: Diurno (8am-1pm) y Nocturno (5:30pm-10pm)"),

    # --- CARRERAS Y DOCENTES (LISTAS COMPLETAS VALIDAS) ---
    "carreras disponibles": ("Programas de Estudios (3 años / Título a Nombre de la Nación):\n\n"
                             "1. Arquitectura de Plataformas y Servicios TI\n"
                             "2. Contabilidad\n"
                             "3. Enfermería Técnica\n"
                             "4. Mecatrónica Automotriz\n"
                             "5. Técnica en Farmacia"),

    "docentes arquitectura": ("Plana Docente - Arquitectura de Plataformas y TI (10):\n\n"
                              "• Hector Jorge Vidalón Jorge (Coord.)\n"
                              "• Pedro Pachas Barrionuevo\n"
                              "• Patricia Janet Benites Yglesias\n"
                              "• Carlos Tasayco Yataco\n"
                              "• Humberto Pablo Vega Cruz\n"
                              "• John Harry Garriazo Castañeda\n"
                              "• Christian Federico Flores Vargas\n"
                              "• José Ricardo Cortez Camacho\n"
                              "• Anthony Francisco Chuan Garcia\n"
                              "• Luis Alberto Chacaltana Arnao"),

    "docentes contabilidad": ("Plana Docente - Contabilidad (9):\n\n"
                              "• Maria Cristina Maguiña Mallma (Coord.)\n"
                              "• Elsa Castilla Almeyda\n"
                              "• Teresa Cajo Rojas\n"
                              "• Marisela Janet Palacios Castillo\n"
                              "• Norma Yolanda Quispe Molina\n"
                              "• Fernando Valderrama Castro\n"
                              "• Luisa Verónica Sanchez Garcia\n"
                              "• Elizabeth Manuela Ore Callirgos\n"
                              "• Coralia Vilca Gonzales"),

    "docentes enfermeria": ("Plana Docente - Enfermería Técnica (8):\n\n"
                            "• Vicente Egusquiza Pozo (Coord.)\n"
                            "• Fabiola Rodriguez Vega\n"
                            "• Diana Noelia Saenz Charaja\n"
                            "• Teresa Liliana Montoya Villasante\n"
                            "• Leonor Nieto Pocomucha\n"
                            "• Lizbeth Fabiola Jara Raraz\n"
                            "• Sandra Oré Calderón\n"
                            "• Mercedes Fuentes Lazo"),

    "docentes mecatronica": ("Plana Docente - Mecatrónica Automotriz (9):\n\n"
                             "• Cesar Augusto Curampa de la Cruz (Coord.)\n"
                             "• Moisés Vargas Soto\n"
                             "• Luis Agustín Mamani Chipana\n"
                             "• Guillermo Carlos Barboza Tello\n"
                             "• Jimmy Quispe Llamoca\n"
                             "• Felix Hans Rivas Calla\n"
                             "• Juan José Montaño Vega\n"
                             "• Washington Ramirez Patiño\n"
                             "• Juan Carlos Pancora Montes"),

    "docentes farmacia": ("Plana Docente - Técnica en Farmacia (8):\n\n"
                          "• Yolanda Suarez Diaz (Coord.)\n"
                          "• Carmen Rosa Acco Gavilan\n"
                          "• Seberino Alberto Canelo Blas\n"
                          "• Miguel Ramiro Huarcaya Fernández\n"
                          "• Fiorela Jeanette Ortiz Ortiz\n"
                          "• Johao Junior Rodriguez Quishac\n"
                          "• Emilia Ramirez Arnao\n"
                          "• Shannon Calderon Quispe"),

    "docentes empleabilidad": ("Plana Docente - Empleabilidad y Transversales (10):\n\n"
                               "• Nilton Aquiles Michuy Suyo\n"
                               "• Richard Mario Celis Calero\n"
                               "• Daniel Quispe De La Torre\n"
                               "• Juan Leopoldo Ranilla Medina\n"
                               "• Wilmer Alarcon Mayta\n"
                               "• Daniel Heli Flores Niño\n"
                               "• Javier Alarcon Mayta\n"
                               "• Lucia Lila Mendoza Huertas\n"
                               "• Miguel Valerio Millones Yauri\n"
                               "• Marilu Carpio Perez"),

    # --- SERVICIOS Y BECAS ---
    "becas disponibles": ("Becas y Beneficios:\n\n"
                          "🥇 100% Dscto Matrícula: Primeros puestos de cada ciclo.\n"
                          "🎖️ 50% Dscto Matrícula: Servicio Militar Acuartelado.\n"
                          "📋 Requisitos: Constancia de notas o carnet de FF.AA."),

    "servicios estudiantes": ("Servicios Complementarios:\n\n"
                              "• Biblioteca Virtual (24/7)\n"
                              "• Tópico de Salud\n"
                              "• Servicio Piscopedagógico\n"
                              "• Bolsa de Trabajo\n"
                              "• Intranet del Estudiante"),
                              
    "libro reclamaciones": ("Libro de Reclamaciones Virtual:\n"
                            "Disponible para registrar quejas o reclamos sobre servicios.\n"
                            "Acceso: https://iestpjva.edu.pe/trasparencia/reclamos")
}


STOPWORDS = {"el", "la", "de", "en", "y", "que", "los", "las", "un", "una", "quisiera", "me", "explicaras"}

def normalize_text(text):
    text = text.lower().strip()
    for old, new in {"á":"a", "é":"e", "í":"i", "ó":"o", "ú":"u"}.items(): text = text.replace(old, new)
    return text

# ============================================================================
# LOGICA DE MAPEO UNIVERSAL (RESTAURADO PARA V7.1)
# ============================================================================
def check_universal_map(query_norm):
    """Mapea palabras clave a respuestas FAQ fijas."""
    universal_map = {
        # Procesos
        "matricula": "proceso matricula",
        "matricularme": "proceso matricula",
        "inscripcion": "requisitos admision",
        "postular": "requisitos admision",
        
        # Docentes
        "farmacia": "docentes farmacia",
        "enfermeria": "docentes enfermeria",
        "computacion": "docentes arquitectura",
        "arquitectura": "docentes arquitectura",
        "contabilidad": "docentes contabilidad",
        "mecatronica": "docentes mecatronica",
        "empleabilidad": "docentes empleabilidad",
        
        # Dinero
        "costo": "cuanto cuesta matricula",
        "pago": "cuanto cuesta matricula",
        "mensualidad": "cuanto cuesta matricula",
        
        # Otros
        "director": "quienes autoridades",
        "beca": "becas disponibles",
        "ubicacion": "donde esta instituto"
    }

    # Revisar si hay coincidencia de palabra clave
    for keyword, faq_key in universal_map.items():
        if keyword in query_norm:
            # Filtro para evitar falsos positivos
            # Ej: "cuanto duran las carreras de farmacia" -> No debe dar docentes
            is_duration_query = any(w in query_norm for w in ["duracion", "tiempo", "años", "semestres", "malla"])
            if faq_key.startswith("docentes") and is_duration_query:
                continue
                
            if faq_key in FAQ:
                return FAQ[faq_key]
    return None

def match_faq(query):
    query_norm = normalize_text(query)
    best_match = None
    best_score = 0.75
    
    for key, val in FAQ.items():
        score = SequenceMatcher(None, query_norm, key).ratio()
        if key in query_norm: score += 0.3
        if score > best_score:
            best_score = score
            best_match = val
            
    return best_match

def semantic_search(query, pdf_context, web_context):
    keywords = [w for w in normalize_text(query).split() if len(w)>3 and w not in STOPWORDS]
    if not keywords: return None
    
    full = (pdf_context + "\n" + web_context).split('\n\n')
    best_para = None
    max_score = 0
    
    for para in full:
        score = sum(para.lower().count(kw) for kw in keywords)
        if score > max_score:
            max_score = score
            best_para = para
            
    if max_score >= 2:
        return best_para
    return None

def get_smart_response(user_message, pdf_context, web_context, ai_fallback_func):
    """
    Motor V7.1:
    1. Check Universal Map (Prioridad Alta - Recuperado)
    2. Check FAQ Fuzzy (Prioridad Media)
    3. Check Complex Intent OR Generic Search (Inyección IA)
    """
    query_norm = normalize_text(user_message)
    
    # 0. DETECTAR INTENCIÓN COMPLEJA
    # Si pide explicación, saltamos las respuestas rápidas y vamos directo a la IA inyectada
    complex_triggers = ["explicar", "explica", "detalle", "detallado", "paso", "procedimiento", "como hago", "guia"]
    is_complex = any(w in query_norm for w in complex_triggers)
    
    evidence = []
    
    # --- FASE 1: RESPUESTAS RÁPIDAS (Solo si NO es una petición compleja) ---
    if not is_complex:
        # A. Mapeo Universal (Recuperado: "costos" -> FAQ)
        uni_match = check_universal_map(query_norm)
        if uni_match:
            print("[SmartResponse] 🎯 Match Universal Map -> FAQ")
            return (uni_match, "faq")
            
        # B. Match Fuzzy
        faq_hit = match_faq(user_message)
        if faq_hit:
            print("[SmartResponse] ✅ Match FAQ Fuzzy")
            return (faq_hit, "faq")

    # --- FASE 2: RECOLECCIÓN DE EVIDENCIA (Para IA o Search Fallback) ---
    
    # Buscamos en FAQ igual (para dárselo a la IA si es compleja)
    if is_complex:
        uni_match = check_universal_map(query_norm)
        if uni_match: evidence.append(f"DATOS FAQ: {uni_match}")
        
    faq_hit = match_faq(user_message)
    if faq_hit: evidence.append(f"DATOS FAQ FUZZY: {faq_hit}")

    # Buscamos en Documentos
    search_hit = semantic_search(user_message, pdf_context, web_context)
    if search_hit:
        # Si NO es compleja y no hubo FAQ antes, mostramos Search...
        # PERO filtro antipático: Si el search es "Página 46..." y no es compleja, 
        # mejor dejamos que la IA lo arregle si tenemos capacidad.
        # Por ahora mantenemos comportamiento: Simple -> Search limpia.
        if not is_complex:
             # Verificamos si es un "chunk feo"
             if "--- página" in search_hit.lower() or "resolu ción" in search_hit.lower():
                 print("[SmartResponse] ⚠️ Search encontró fragmento crudo, delegando a IA para limpieza.")
                 evidence.append(f"FRAGMENTO CRUDO: {search_hit}")
             else:
                print("[SmartResponse] 🔍 Match Semántico Directo")
                return (f"Según documentación:\n{search_hit[:500]}...", "search")
        else:
            evidence.append(f"FRAGMENTO DOCS: {search_hit}")

    # --- FASE 3: DELEGACIÓN A IA (Compleja o Fallback de Calidad) ---
    print(f"[SmartResponse] 🧠 Delegando a IA (Compleja={is_complex}). Evidencia: {len(evidence)}")
    
    ai_manager = get_ai_manager()
    combined_evidence = "\n\n".join(evidence) if evidence else None
    
    ai_resp = ai_manager.generate_response(
        user_message=user_message,
        pdf_context=pdf_context,
        web_context=web_context,
        smart_context_injection=combined_evidence # Inyección V7
    )
    
    if ai_resp: return (ai_resp, "ai")
        
    return ("Lo siento, no tengo información precisa sobre eso en este momento.", "error")
