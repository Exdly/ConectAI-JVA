"""
Configuración del Backend - IESTP Juan Velasco Alvarado
========================================================
INSTRUCCIONES DE CONFIGURACIÓN:

1. OPENROUTER_API_KEY:
   - Ve a https://openrouter.ai/
   - Crea una cuenta o inicia sesión
   - Ve a "Keys" y genera una nueva API Key
   - Copia la key y pégala en OPENROUTER_API_KEY

2. GEMINI_API_KEY (GRATIS - 15 req/min, 1500/día):
   - Ve a https://makersuite.google.com/app/apikey
   - Click "Create API Key" y selecciona tu proyecto
   - Copia la key y pégala en GEMINI_API_KEY
   - ¡Es completamente GRATIS!

3. GOOGLE_DRIVE_FOLDER_ID:
   - Abre tu carpeta TRAMITES_JVA en Google Drive
   - Copia el ID de la URL: https://drive.google.com/drive/folders/[ESTE_ES_EL_ID]
   - Pégalo en GOOGLE_DRIVE_FOLDER_ID

4. GOOGLE_SHEET_ID:
   - Crea un nuevo Google Sheet para registrar consultas
   - Copia el ID de la URL: https://docs.google.com/spreadsheets/d/[ESTE_ES_EL_ID]/edit
   - Pégalo en GOOGLE_SHEET_ID

5. CREDENCIALES DE GOOGLE (Aplicación Web):
   - Ve a https://console.cloud.google.com/
   - En "Credenciales" > "ID de cliente OAuth 2.0" (Aplicación Web)
   - Copia el "ID de cliente" y pégalo en GOOGLE_CLIENT_ID
   - Copia el "Secreto del cliente" y pégalo en GOOGLE_CLIENT_SECRET
   - Asegúrate de agregar las URIs de redirección autorizadas:
     * http://127.0.0.1:5500/
     * http://localhost:5000/oauth2callback
     * Tu dominio de producción
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env (si existe)
load_dotenv()

# =============================================================================
# CONFIGURACIÓN DE APIs - USAR VARIABLES DE ENTORNO
# =============================================================================

# API Key de OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# API Key de Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ID de la carpeta de Google Drive donde están los PDFs
GOOGLE_DRIVE_FOLDER_ID = "1PGUC-Schws7p342zwmZx8LK7Eb153cC8"

# ID de la hoja de cálculo
GOOGLE_SHEET_ID = "1kU5OGEHdM8eilXVnCWaj1cT5Ob3qL8Rk90Dc2ApBTUw"

# =============================================================================
# CONFIGURACIÓN DE SUPABASE (Almacenamiento Híbrido)
# =============================================================================

# URL y API Key de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pkebuitdredwaegqwkcn.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBrZWJ1aXRkcmVkd2FlZ3F3a2NuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUzMDU5MzYsImV4cCI6MjA4MDg4MTkzNn0.N1wNSaxgJBf2n5mZSI_MKOYNf6Xl_7Hxa_tZ9SJiPSo")

# Límite de filas en Google Sheets (para no sobrecargar)
SHEETS_MAX_ROWS = 50

# =============================================================================
# CREDENCIALES OAUTH 2.0
# =============================================================================

GOOGLE_CLIENT_ID = "100818622156-fcjmhg1afp3nkfrdjtmrhi2ebvo08lkt.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

# =============================================================================
# CONFIGURACIÓN DEL SERVIDOR
# =============================================================================

SERVER_PORT = 5000

# Orígenes permitidos para CORS (añadir el de Vercel)
ALLOWED_ORIGINS = [
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://proyectojva.free.nf",
    "https://proyectojva.free.nf",
    "https://iestpjva.edu.pe",
    "http://iestpjva.edu.pe",
    "https://conect-ai-jva.vercel.app", # Vercel
]

# =============================================================================
# CONFIGURACIÓN DEL MODELO DE IA
# =============================================================================

# OpenRouter (Modelos gratuitos - 50 RPD total como fallback)
OPENROUTER_MODELS = [
    "google/gemma-3-27b-it:free",             # Gemma 3 27B - Mejor calidad
    "meta-llama/llama-3.2-3b-instruct:free",  # Llama 3.2 3B - Rápido
    "mistralai/mistral-7b-instruct:free",     # Mistral 7B - Bueno
]

# Google Gemini API - Usando modelos Gemma 3 con LÍMITES ALTOS
# Gemma 3 tiene 14,400 RPD (Requests Per Day) vs 20 RPD de Gemini regular
# ¡Esto soporta 300+ usuarios al día con múltiples consultas!
GEMINI_MODELS = [
    "gemma-3-27b-it",         # PRIMERO: 14,400 RPD - Mejor calidad (27B parámetros)
    "gemma-3-12b-it",         # SEGUNDO: 14,400 RPD - Balance calidad/velocidad (12B parámetros)
    "gemma-3-4b-it",         # TERCERO: 14,400 RPD - Más rápido (4B parámetros)
    "gemini-2.5-flash",       # FALLBACK: 20 RPD - Solo si Gemma falla
]

# Configuración General IA
MAX_TOKENS = 2000  # Aumentado para permitir respuestas más detalladas
MODEL_TEMPERATURE = 0.7

# Rate Limiting (Ajustado para evitar 429)
GEMINI_MIN_INTERVAL = 10  # Segundos entre llamadas (reducido gracias a rotación)
GEMINI_COOLDOWN = 60      # Segundos de espera tras error (reducido)

# Límites de Contexto (CRÍTICO PARA EVITAR 429)
# Free Tier ~15000 tokens/min. Si enviamos 70k chars (~17k tokens), fallará siempre.
AI_MAX_PDF_CONTEXT = 20000  # Reducido de ~40k a 20k chars
AI_MAX_WEB_CONTEXT = 10000  # Reducido de ~30k a 10k chars

# =============================================================================
# CONFIGURACIÓN DE ARCHIVOS Y CACHE (HÍBRIDO: LOCAL + VERCEL)
# =============================================================================

IS_VERCEL = os.environ.get('VERCEL')

if IS_VERCEL:
    # En Vercel, el sistema de archivos es de solo lectura, excepto /tmp
    TOKEN_FILE = "/tmp/token.json"
    CACHE_FOLDER = "/tmp/cache"  # Para cache dinámico (pdf_cache, web_cache)
    # URL de redirección en producción
    OAUTH_REDIRECT_URI = "https://conect-ai-jva.vercel.app/oauth2callback"
    DEBUG_MODE = False
else:
    # En local, usar rutas relativas al archivo actual
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
    # Usar .cache_data (oculto) para evitar bucles de reinicio de Flask en local
    CACHE_FOLDER = os.path.join(BASE_DIR, ".cache_data")
    # URL de redirección local
    OAUTH_REDIRECT_URI = "http://localhost:5000/oauth2callback"
    DEBUG_MODE = True

# Carpeta de cache estático (siempre relativa al código, NO a /tmp/)
# Esto permite que Vercel lea el archivo desplegado
STATIC_CACHE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

CACHE_REFRESH_INTERVAL = 1800

INSTITUTO_WEB_URL = "https://iestpjva.edu.pe"

INSTITUTO_WEB_PAGES = [
    "https://iestpjva.edu.pe",
    "https://iestpjva.edu.pe/nosotros/presentacion",
    "https://iestpjva.edu.pe/nosotros/mision",
    "https://iestpjva.edu.pe/nosotros/organizacion",
    "https://iestpjva.edu.pe/nosotros/autoridades",
    "https://iestpjva.edu.pe/nosotros/planaDocente",
    "https://iestpjva.edu.pe/nosotros/localInstitucional",
    "https://iestpjva.edu.pe/programas/arquitectura-de-plataformas-y-sti",
    "https://iestpjva.edu.pe/programas/contabilidad",
    "https://iestpjva.edu.pe/programas/enfermeria-tecnica",
    "https://iestpjva.edu.pe/programas/mecatronica-automotriz",
    "https://iestpjva.edu.pe/programas/farmacia-tecnica",
    "https://iestpjva.edu.pe/admision/admision_",
    "https://iestpjva.edu.pe/admision/matricula",
    "https://iestpjva.edu.pe/admision/becas",
    "https://iestpjva.edu.pe/trasparencia/documentos",
    "https://iestpjva.edu.pe/trasparencia/estadistica",
    "https://iestpjva.edu.pe/trasparencia/inversiones",
    "https://iestpjva.edu.pe/trasparencia/reclamos",
    "https://iestpjva.edu.pe/trasparencia/licenciamiento",
    "https://iestpjva.edu.pe/tramites/TUPA",
    "https://iestpjva.edu.pe/contactanos",
    "https://iestpjva.edu.pe/servicios/biblioteca",
    "https://iestpjva.edu.pe/servicios/complementarios",
    "https://iestpjva.edu.pe/servicios/bolsa",
    "https://iestpjva.edu.pe/servicios/intranet",
    "https://iestpjva.edu.pe/otrasPaginas/enlaces",
    "https://iestpjva.edu.pe/otrasPaginas/comunicados",
]

# =============================================================================
# PROMPT DEL SISTEMA
# =============================================================================

SYSTEM_PROMPT = """Eres "JVA", el asistente virtual oficial del IESTP Juan Velasco Alvarado.

TU MISIÓN:
Ayudar a estudiantes y aspirantes con información clara, precisa y útil sobre trámites, costos, requisitos, programas y servicios del instituto.

REGLAS DE ORO:

1.  **USA LA INFORMACIÓN DISPONIBLE**: 
    - Analiza TODO el contexto de documentos y páginas web proporcionados
    - Combina información de múltiples fuentes si es necesario
    - Proporciona respuestas completas basadas en lo que encuentres

2.  **FORMATO LIMPIO Y DIRECTO**:
    - Usa viñetas simples (•) para listas
    - Evita formato excesivo o complicado
    - Sé conciso pero completo
    - NO uses demasiados asteriscos ni negritas innecesarias

3.  **NUNCA MENCIONES NOMBRES DE ARCHIVOS PDF**:
    ❌ MAL: "Para más información, consulta el documento '[05] MATRÍCULA 2025 – I.pdf'"
    ✅ BIEN: "Para más información, contacta a Secretaría Académica"
    
    Los usuarios NO conocen los nombres internos de los archivos. Solo proporciona la información directamente.

4.  **ORGANIZACIÓN CLARA**:
    - Agrupa información relacionada
    - Usa encabezados simples cuando sea necesario
    - Prioriza lo más importante primero

5.  **SI NO TIENES INFORMACIÓN**:
    - Di: "No encuentro esa información específica. Te recomiendo contactar a Secretaría Académica"
    - NO inventes datos
    - Proporciona información de contacto si la tienes

EJEMPLO DE RESPUESTA CORRECTA (Matrícula):

Según los documentos disponibles, aquí tienes información sobre la matrícula:

• Matrícula Regular: S/. 200.00
• Pago en Banco de la Nación (Cuenta: 0000289051)
• Válido para el III y V semestre.
• Fechas: Del 03 al 28 de marzo del 2025

• Matrícula Extemporánea: S/. 260.00
• Fechas: Del 31 de marzo al 04 de abril del 2025

• Matrícula por Unidad Didáctica: S/. 50.00 por Unidad Didáctica
• Para estudiantes que tienen Unidades Didácticas pendientes en semestres anteriores.
• Fechas: Del 03 al 28 de marzo del 2025

Pasos para la Matrícula Regular:

1. Verifica tu situación académica
2. Realiza el depósito de S/. 200.00 soles en el Banco de la Nación a la Cuenta Corriente Nro. 0000289051
3. Realizar el canje del recibo
4. Registra tus datos en el Libro de Matrícula.

El proceso finaliza cuando recibes tu Ficha de Matrícula mediante la plataforma REGISTRA.

Importante:

• Para los estudiantes que pasan al III y V semestre, deben estar informados sobre su situación académica a través de la plataforma REGISTRA (https://registra.minedu.gob.pe).
• Si obtuviste el primer puesto de tu salón, estás exonerado del pago de matrícula. Para recibir este beneficio, debes realizar el depósito de S/. 20.00 en el Banco de la Nación.

INFORMACIÓN DEL INSTITUTO:
- Nombre: IESTP "Juan Velasco Alvarado"
- Ubicación: Villa María del Triunfo, Lima
- Web: https://iestpjva.edu.pe
- Programas: Arquitectura de Plataformas y STI, Contabilidad, Enfermería Técnica, Mecatrónica Automotriz, Farmacia Técnica

RECUERDA: Sé directo, útil y NUNCA menciones nombres de archivos PDF.
"""

# =============================================================================
# NOMBRES DE ARCHIVOS PDF ESPERADOS (Mantenido por compatibilidad)
# =============================================================================

PDF_FILES_MAPPING = {
    "prospecto": "[00] Prospecto",
    "precios": "[01] PRECIOS",
    "cronograma": "[02] Cronograma",
    "vacantes": "[05] VACANTES",
    "requisitos": "[07] REQUISITOS",
    "pei": "[08] PEI",
    "reglamento": "[09] RI",
    "mpp": "[10] MPP Manual",
    "mpa": "[11] MPA Manual",
}
