"""
Configuración del Backend - IESTP Juan Velasco Alvarado
========================================================
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

# =============================================================================
# CONFIGURACIÓN DE APIs - USAR VARIABLES DE ENTORNO
# =============================================================================

# API Key de OpenRouter (cargada desde .env o variables de entorno de Vercel)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# API Key de Google Gemini (cargada desde .env o variables de entorno de Vercel)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ID de la carpeta de Google Drive donde están los PDFs
GOOGLE_DRIVE_FOLDER_ID = "1PGUC-Schws7p342zwmZx8LK7Eb153cC8"

# ID del Google Sheet para registro de consultas
GOOGLE_SHEET_ID = "1kU5OGEHdM8eilXVnCWaj1cT5Ob3qL8Rk90Dc2ApBTUw"

# =============================================================================
# CREDENCIALES OAUTH 2.0
# =============================================================================

GOOGLE_CLIENT_ID = "100818622156-fcjmhg1afp3nkfrdjtmrhi2ebvo08lkt.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

# =============================================================================
# CONFIGURACIÓN DEL SERVIDOR
# =============================================================================

SERVER_PORT = 5000

# Orígenes permitidos para CORS
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://proyectojva.free.nf",
    "https://proyectojva.free.nf",
    "https://iestpjva.edu.pe",
    "http://iestpjva.edu.pe",
    # Dominios de Vercel
    "https://conect-ai-jva.vercel.app",
    "https://*.vercel.app",
]

# =============================================================================
# CONFIGURACIÓN DEL MODELO DE IA
# =============================================================================

OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
]

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

MAX_TOKENS = 2000
MODEL_TEMPERATURE = 0.7
GEMINI_MIN_INTERVAL = 10
GEMINI_COOLDOWN = 60

# =============================================================================
# CONFIGURACIÓN DE ARCHIVOS Y CACHE
# =============================================================================

# Detectar si estamos en Vercel
IS_VERCEL = os.environ.get('VERCEL')

if IS_VERCEL:
    # En Vercel, el sistema de archivos es de solo lectura, excepto /tmp
    TOKEN_FILE = "/tmp/token.json"
    CACHE_FOLDER = "/tmp/cache_pdfs"
    # URL de redirección en producción
    OAUTH_REDIRECT_URI = "https://conect-ai-jva.vercel.app/oauth2callback"
    DEBUG_MODE = False
else:
    # En local, usar rutas relativas al archivo actual
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
    CACHE_FOLDER = os.path.join(BASE_DIR, "cache_pdfs")
    # URL de redirección local
    OAUTH_REDIRECT_URI = "http://localhost:5000/oauth2callback"
    DEBUG_MODE = True

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

4.  **ORGANIZACIÓN CLARA**:
    - Agrupa información relacionada
    - Usa encabezados simples cuando sea necesario
    - Prioriza lo más importante primero

5.  **SI NO TIENES INFORMACIÓN**:
    - Di: "No encuentro esa información específica. Te recomiendo contactar a Secretaría Académica"
    - NO inventes datos
    - Proporciona información de contacto si la tienes

INFORMACIÓN DEL INSTITUTO:
- Nombre: IESTP "Juan Velasco Alvarado"
- Ubicación: Villa María del Triunfo, Lima
- Web: https://iestpjva.edu.pe
- Programas: Arquitectura de Plataformas y STI, Contabilidad, Enfermería Técnica, Mecatrónica Automotriz, Farmacia Técnica

RECUERDA: Sé directo, útil y NUNCA menciones nombres de archivos PDF.
"""

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
