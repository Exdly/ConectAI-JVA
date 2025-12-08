"""
Módulo de Web Scraping - IESTP Juan Velasco Alvarado
=====================================================
Este módulo extrae información del sitio web oficial del instituto.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import time
import hashlib
import os
import json

from config import (
    INSTITUTO_WEB_URL,
    INSTITUTO_WEB_PAGES,
    CACHE_FOLDER,
    CACHE_REFRESH_INTERVAL
)

class WebScraper:
    """Clase para extraer información del sitio web del instituto."""
    
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.cache_file = os.path.join(CACHE_FOLDER, "web_cache.json")
        self._ensure_cache_folder()
        self._load_cache()
    
    def _ensure_cache_folder(self):
        """Crea la carpeta de cache si no existe."""
        if not os.path.exists(CACHE_FOLDER):
            os.makedirs(CACHE_FOLDER)
    
    def _load_cache(self):
        """Carga el cache desde archivo."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = data.get('content', {})
                    self.cache_timestamps = data.get('timestamps', {})
                print(f"[WebScraper] Cache cargado: {len(self.cache)} páginas")
            except Exception as e:
                print(f"[WebScraper] Error cargando cache: {e}")
    
    def _save_cache(self):
        """Guarda el cache en archivo."""
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
        if url not in self.cache_timestamps:
            return False
        age = time.time() - self.cache_timestamps[url]
        return age < CACHE_REFRESH_INTERVAL
    
    def _extract_text_from_page(self, url: str) -> Optional[str]:
        """Extrae texto limpio de una página web."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # verify=False para evitar errores de certificado SSL comunes en sitios institucionales
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Eliminar scripts, estilos y elementos no relevantes
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
                element.decompose()
            
            # Extraer texto del contenido principal
            # Intentar encontrar el contenedor principal más probable
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.find('div', id='content') or soup.body
            
            if main_content:
                # Obtener texto con saltos de línea preservados y limpiar espacios
                text_parts = []
                for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'td', 'th', 'span', 'a', 'div']):
                     # Ignorar elementos vacíos o solo espacios
                    text = element.get_text(strip=True)
                    if text and len(text) > 3: # Filtro mínimo de longitud
                        text_parts.append(text)
                
                # Eliminar duplicados consecutivos (común en menús/headers mal limpiados)
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

    def clean_cache(self):
        """Elimina entradas del cache que no están en la configuración actual."""
        current_urls = set(INSTITUTO_WEB_PAGES)
        cached_urls = list(self.cache.keys())
        removed_count = 0
        
        for url in cached_urls:
            if url not in current_urls:
                del self.cache[url]
                if url in self.cache_timestamps:
                    del self.cache_timestamps[url]
                removed_count += 1
        
        if removed_count > 0:
            print(f"[WebScraper] Limpiadas {removed_count} entradas obsoletas del cache")
            self._save_cache()

    def get_all_website_content(self, force_refresh: bool = False) -> str:
        """
        Obtiene el contenido de todas las páginas configuradas.
        """
        # Primero limpiar cache de URLs viejas
        self.clean_cache()
        
        all_content = []
        print(f"[WebScraper] Procesando {len(INSTITUTO_WEB_PAGES)} páginas configuradas...")
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # Silenciar advertencias SSL

        for i, url in enumerate(INSTITUTO_WEB_PAGES):
            try:
                content = self.get_page_content(url, force_refresh)
                if content:
                    all_content.append(f"\n{'='*50}\nPÁGINA WEB: {url}\n{'='*50}\n{content}")
                else:
                    print(f"[WebScraper] ADVERTENCIA: No se pudo obtener contenido de {url}")
            except Exception as e:
                print(f"[WebScraper] Error fatal procesando {url}: {e}")
        
        return '\n\n'.join(all_content)
    
    def get_pdfs_from_website(self) -> List[Dict]:
        """Obtiene la lista de PDFs disponibles en el sitio web."""
        all_pdfs = []
        seen_urls = set()
        
        for url in INSTITUTO_WEB_PAGES:
            pdfs = self._extract_pdfs_from_page(url)
            for pdf in pdfs:
                if pdf['url'] not in seen_urls:
                    seen_urls.add(pdf['url'])
                    all_pdfs.append(pdf)
        
        print(f"[WebScraper] Encontrados {len(all_pdfs)} PDFs en el sitio web")
        return all_pdfs
    
    def download_pdf_from_url(self, url: str) -> Optional[bytes]:
        """Descarga un PDF desde una URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            print(f"[WebScraper] Error descargando PDF {url}: {e}")
            return None
    
    def search_in_website(self, query: str) -> str:
        """
        Busca información relevante en el contenido del sitio web.
        
        Args:
            query: Término de búsqueda
            
        Returns:
            Contenido relevante encontrado
        """
        query_lower = query.lower()
        relevant_content = []
        
        for url in INSTITUTO_WEB_PAGES:
            content = self.get_page_content(url)
            if content and query_lower in content.lower():
                relevant_content.append(f"--- {url} ---\n{content[:5000]}")
        
        return '\n\n'.join(relevant_content) if relevant_content else ""

# Instancia global (singleton)
_web_scraper = None

def get_web_scraper() -> WebScraper:
    """Obtiene la instancia del web scraper."""
    global _web_scraper
    if _web_scraper is None:
        _web_scraper = WebScraper()
    return _web_scraper
