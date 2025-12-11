"""
Módulo de Web Scraping - IESTP Juan Velasco Alvarado
=====================================================
Extrae información del sitio web oficial del instituto.

SOLUCIÓN HÍBRIDA:
- Cache estático (static_web_cache.json) generado con Playwright
- Funciona en Vercel sin dependencias pesadas
- Fallback a requests para páginas no cacheadas

Para actualizar el cache estático (requiere Playwright instalado):
    python -c "from web_scraper import scrape_all_pages; scrape_all_pages()"
"""

import os
import json
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime

from config import (
    INSTITUTO_WEB_PAGES,
    CACHE_FOLDER,
    STATIC_CACHE_FOLDER,
    CACHE_REFRESH_INTERVAL
)


class WebScraper:
    """Clase para extraer información del sitio web del instituto."""
    
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.cache_file = os.path.join(CACHE_FOLDER, "web_cache.json")
        
        # Cache estático (siempre en el código desplegado, no en /tmp/)
        self.static_cache_file = os.path.join(STATIC_CACHE_FOLDER, "static_web_cache.json")
        self.static_cache: Dict[str, dict] = {}
        
        self._ensure_cache_folder()
        self._load_static_cache()
        self._load_cache()
    
    def _ensure_cache_folder(self):
        """Crea la carpeta de cache si no existe."""
        try:
            if not os.path.exists(CACHE_FOLDER):
                os.makedirs(CACHE_FOLDER)
        except Exception as e:
            print(f"[WebScraper] No se pudo crear carpeta cache: {e}")
    
    def _load_static_cache(self):
        """Carga el cache estático generado con Playwright."""
        if os.path.exists(self.static_cache_file):
            try:
                with open(self.static_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.static_cache = data.get('pages', {})
                    
                    # Pre-poblar cache con contenido estático
                    loaded_count = 0
                    for url, page_data in self.static_cache.items():
                        if page_data.get('success') and page_data.get('content'):
                            self.cache[url] = page_data['content']
                            self.cache_timestamps[url] = time.time()
                            loaded_count += 1
                    
                    metadata = data.get('metadata', {})
                    print(f"[WebScraper] Cache estático cargado: {loaded_count} páginas")
                    print(f"[WebScraper] Generado: {metadata.get('generated_at', 'desconocido')}")
            except Exception as e:
                print(f"[WebScraper] Error cargando cache estático: {e}")
        else:
            print(f"[WebScraper] AVISO: No existe cache estático")
            print(f"[WebScraper] Ejecuta: python -c \"from web_scraper import scrape_all_pages; scrape_all_pages()\"")
    
    def _load_cache(self):
        """Carga el cache dinámico desde archivo."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    dynamic_cache = data.get('content', {})
                    dynamic_timestamps = data.get('timestamps', {})
                    
                    for url, content in dynamic_cache.items():
                        if url not in self.cache:
                            self.cache[url] = content
                            self.cache_timestamps[url] = dynamic_timestamps.get(url, 0)
                    
                print(f"[WebScraper] Cache dinámico: {len(dynamic_cache)} páginas adicionales")
            except Exception as e:
                print(f"[WebScraper] Error cargando cache dinámico: {e}")
    
    def _save_cache(self):
        """Guarda el cache dinámico en archivo."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'content': self.cache,
                    'timestamps': self.cache_timestamps
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WebScraper] Error guardando cache: {e}")
    
    def _is_cache_valid(self, url: str) -> bool:
        """Verifica si el cache de una URL es válido."""
        if url in self.static_cache and self.static_cache[url].get('success'):
            return True
        if url not in self.cache_timestamps:
            return False
        age = time.time() - self.cache_timestamps[url]
        return age < CACHE_REFRESH_INTERVAL
    
    def _extract_text_from_page(self, url: str) -> Optional[str]:
        """Extrae texto de una página web (solo HTML estático)."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Detectar SPA
            root_div = soup.find('div', id='root') or soup.find('div', id='app')
            if root_div and len(root_div.get_text(strip=True)) < 100:
                print(f"[WebScraper] {url} es SPA - requiere cache estático")
                return None
            
            # Eliminar elementos no relevantes
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
                element.decompose()
            
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.body
            
            if main_content:
                text_parts = []
                for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'td', 'th', 'span', 'a', 'div']):
                    text = element.get_text(strip=True)
                    if text and len(text) > 3:
                        text_parts.append(text)
                
                # Eliminar duplicados consecutivos
                cleaned_parts = []
                if text_parts:
                    cleaned_parts.append(text_parts[0])
                    for i in range(1, len(text_parts)):
                        if text_parts[i] != text_parts[i-1]:
                            cleaned_parts.append(text_parts[i])
                
                return '\n'.join(cleaned_parts)
            return None
        except Exception as e:
            print(f"[WebScraper] Error extrayendo {url}: {e}")
            return None

    def get_page_content(self, url: str, force_refresh: bool = False) -> Optional[str]:
        """Obtiene el contenido de una página web (con cache)."""
        if not force_refresh and self._is_cache_valid(url):
            print(f"[WebScraper] Usando cache para: {url}")
            return self.cache.get(url)
        
        content = self._extract_text_from_page(url)
        if content:
            self.cache[url] = content
            self.cache_timestamps[url] = time.time()
            self._save_cache()
            print(f"[WebScraper] Extraído de {url}: {len(content)} caracteres")
        return content

    def get_all_website_content(self, force_refresh: bool = False) -> str:
        """Obtiene el contenido de todas las páginas configuradas."""
        all_content = []
        print(f"[WebScraper] Procesando {len(INSTITUTO_WEB_PAGES)} páginas configuradas...")
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        for url in INSTITUTO_WEB_PAGES:
            try:
                content = self.get_page_content(url, force_refresh)
                if content:
                    # ENRIQUECIMIENTO DE CONTEXTO (Deep Fix para Docentes)
                    # Inyectamos el contexto de la sección en cada línea para que RAG no pierda la referencia
                    content = self._enrich_content_with_context(content, url)
                    all_content.append(f"\n{'='*50}\nPÁGINA WEB: {url}\n{'='*50}\n{content}")
            except Exception as e:
                print(f"[WebScraper] Error procesando {url}: {e}")
        
        return '\n\n'.join(all_content)

    def _enrich_content_with_context(self, content: str, url: str) -> str:
        """
        Enriquece el contenido con contexto explícito para mejorar RAG.
        Específicamente para la página de 'planaDocente' donde se mezclan carreras.
        """
        if "planaDocente" not in url:
            return content
            
        lines = content.split('\n')
        enriched_lines = []
        current_section = "INFORMACIÓN GENERAL"
        
        # Headers conocidos en la página de Plana Docente (basado en análisis de cache)
        known_sections = [
            "ARQUITECTURA DE PLATAFORMAS Y SERVICIOS TI",
            "CONTABILIDAD",
            "ENFERMERÍA TÉCNICA",
            "MECATRÓNICA AUTOMOTRIZ",
            "TÉCNICA EN FARMACIA",
            "DOCENTES DE EMPLEABILIDAD"
        ]
        
        found_any_section = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                enriched_lines.append(line)
                continue
                
            # Normalizar para detección
            upper_line = stripped.upper()
            
            # Detectar cambio de sección
            is_header = False
            for sec in known_sections:
                if sec in upper_line:
                    current_section = sec
                    is_header = True
                    found_any_section = True
                    break
            
            if is_header:
                # Marcamos fuertemente el header
                enriched_lines.append(f"\n=== SECCIÓN: {current_section} ===\n{line}")
            elif found_any_section and len(stripped) > 3 and "Ver CV" not in stripped and "IESTP" not in stripped:
                # Inyectamos el contexto en líneas de contenido (nombres de docentes)
                # Formato: [Carrera] Nombre
                enriched_lines.append(f"[{current_section}] {line}")
            else:
                enriched_lines.append(line)
                
        return '\n'.join(enriched_lines)
    
    def search_in_website(self, query: str) -> str:
        """Busca información relevante en el contenido del sitio web."""
        query_lower = query.lower()
        relevant_content = []
        
        for url in INSTITUTO_WEB_PAGES:
            content = self.get_page_content(url)
            if content:
                content = self._enrich_content_with_context(content, url)
                if query_lower in content.lower():
                    relevant_content.append(f"--- {url} ---\n{content[:5000]}")
        
        return '\n\n'.join(relevant_content) if relevant_content else ""


# ============================================================================
# FUNCIONALIDAD DE PLAYWRIGHT (para actualizar cache estático)
# ============================================================================

def scrape_all_pages():
    """
    Extrae contenido de todas las páginas usando Playwright.
    Ejecutar localmente para actualizar el cache estático.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright no está instalado.")
        print("Instálalo con: pip install playwright")
        print("Luego ejecuta: playwright install chromium")
        return
    
    print("=" * 60)
    print("  SCRAPER DE SITIO WEB SPA - IESTP JVA")
    print("=" * 60)
    print(f"\nPáginas a procesar: {len(INSTITUTO_WEB_PAGES)}")
    
    static_cache_file = os.path.join(STATIC_CACHE_FOLDER, "static_web_cache.json")
    print(f"Archivo de salida: {static_cache_file}\n")
    
    results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_pages": len(INSTITUTO_WEB_PAGES),
            "successful": 0,
            "failed": 0
        },
        "pages": {}
    }
    
    with sync_playwright() as p:
        print("[1/3] Iniciando navegador Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        print("[2/3] Extrayendo contenido de páginas...\n")
        
        for i, url in enumerate(INSTITUTO_WEB_PAGES, 1):
            print(f"[{i}/{len(INSTITUTO_WEB_PAGES)}] Procesando...")
            data = _extract_page_with_playwright(page, url)
            results["pages"][url] = data
            
            if data["success"]:
                results["metadata"]["successful"] += 1
                preview = data["content"][:100].replace('\n', ' ')
                print(f"  [OK] ({len(data['content'])} chars): {preview}...")
            else:
                results["metadata"]["failed"] += 1
                print(f"  [X] Sin contenido útil")
            
            time.sleep(0.5)
        
        browser.close()
    
    # Asegurar que la carpeta existe
    os.makedirs(os.path.dirname(static_cache_file), exist_ok=True)
    
    print(f"\n[3/3] Guardando cache estático...")
    with open(static_cache_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"  Exitosas: {results['metadata']['successful']}")
    print(f"  Fallidas: {results['metadata']['failed']}")
    print(f"  Archivo: {static_cache_file}")
    print(f"  Tamaño: {os.path.getsize(static_cache_file) / 1024:.1f} KB")
    print("=" * 60)


def _extract_page_with_playwright(page, url: str) -> dict:
    """Extrae contenido de una página SPA con Playwright."""
    try:
        print(f"  -> Navegando a: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        
        # Eliminar elementos no deseados
        page.evaluate("""
            () => {
                const unwanted = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript'];
                unwanted.forEach(tag => {
                    document.querySelectorAll(tag).forEach(el => el.remove());
                });
            }
        """)
        
        # Extraer texto
        content = page.evaluate("""
            () => {
                const main = document.querySelector('main') || 
                            document.querySelector('article') || 
                            document.querySelector('.content') ||
                            document.querySelector('#content') ||
                            document.querySelector('#root') ||
                            document.body;
                
                if (!main) return '';
                
                const elements = main.querySelectorAll('h1, h2, h3, h4, p, li, td, th, span, a, div');
                const texts = [];
                const seen = new Set();
                
                elements.forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && text.length > 3 && !seen.has(text)) {
                        seen.add(text);
                        texts.push(text);
                    }
                });
                
                return texts.join('\\n');
            }
        """)
        
        title = page.title()
        
        return {
            "url": url,
            "title": title,
            "content": content,
            "extracted_at": datetime.now().isoformat(),
            "success": bool(content and len(content) > 50)
        }
    except Exception as e:
        print(f"  [X] Error en {url}: {e}")
        return {
            "url": url,
            "title": "",
            "content": "",
            "extracted_at": datetime.now().isoformat(),
            "success": False,
            "error": str(e)
        }


# Singleton
_web_scraper = None

def get_web_scraper() -> WebScraper:
    """Obtiene la instancia del web scraper."""
    global _web_scraper
    if _web_scraper is None:
        _web_scraper = WebScraper()
    return _web_scraper
