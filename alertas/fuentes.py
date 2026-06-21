"""Descarga de fuentes, extracción de enlaces y filtrado por keywords."""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .modelo import Resultado, ResultadoFuente, normaliza

log = logging.getLogger("alertas.fuentes")

# User-Agent realista: algunos portales de la Administración rechazan
# peticiones sin cabecera de navegador.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}


def _contiene(texto_norm: str, keyword: str) -> bool:
    """Match por PREFIJO de palabra, token a token.

    Cada palabra de la keyword admite sufijos (plurales/derivados) pero debe empezar
    en límite de palabra. Así:
      - 'interino'            casa 'interinos', 'interinidad'
      - 'comision de servicio' casa 'comisiones de servicio'
      - 'maestro'            casa 'maestros'
    pero 'al'/'pt' NO casarían dentro de 'portal'/'apto' (no hay límite de palabra antes).
    """
    tokens = normaliza(keyword).split()
    patron = r"\b" + r"\w*\s+".join(re.escape(t) for t in tokens) + r"\w*"
    return re.search(patron, texto_norm) is not None


def es_relevante(titulo: str, incluir: list[str], excluir: list[str]) -> bool:
    """True si el título contiene alguna keyword de `incluir` y ninguna de `excluir`."""
    t = normaliza(titulo)
    if any(_contiene(t, x) for x in excluir):
        return False
    return any(_contiene(t, x) for x in incluir)


def extrae_enlaces(html: str, base: str, min_long: int) -> list[tuple[str, str]]:
    """Devuelve [(titulo, url_absoluta)] de todos los <a> con texto significativo."""
    soup = BeautifulSoup(html, "html.parser")
    vistos: set[str] = set()
    salida: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        titulo = " ".join(a.get_text(" ", strip=True).split())
        href = a["href"].strip()
        if not titulo or len(titulo) < min_long:
            continue
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urljoin(base, href)
        if url in vistos:
            continue
        vistos.add(url)
        salida.append((titulo, url))
    return salida


def _descarga_requests(url: str, timeout: int) -> str:
    """Descarga ligera con requests (para webs que sirven HTML en servidor)."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _descarga_playwright(url: str, timeout: int) -> str:
    """Descarga con navegador headless (para webs que renderizan por JavaScript).

    Import perezoso: Playwright sólo se necesita para fuentes 'render: js', así que no
    se importa salvo que haga falta. Requiere `playwright install chromium`.
    """
    from playwright.sync_api import sync_playwright  # import perezoso

    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        try:
            pagina = navegador.new_page(user_agent=HEADERS["User-Agent"])
            pagina.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            return pagina.content()
        finally:
            navegador.close()


def procesa_fuente(fuente: dict, incluir: list[str], excluir: list[str],
                   opciones: dict) -> ResultadoFuente:
    """Descarga una fuente y devuelve sus resultados relevantes (sin deduplicar aún).

    `fuente["render"] == "js"` usa navegador headless; en otro caso, requests.
    """
    nombre = fuente["nombre"]
    timeout = opciones.get("timeout", 25)
    usa_js = fuente.get("render") == "js"
    try:
        html = (_descarga_playwright(fuente["url"], timeout) if usa_js
                else _descarga_requests(fuente["url"], timeout))

        enlaces = extrae_enlaces(
            html, fuente.get("base", fuente["url"]),
            opciones.get("min_long_titulo", 12),
        )
        relevantes = [
            Resultado(fuente=nombre, titulo=t, url=u)
            for (t, u) in enlaces
            if es_relevante(t, incluir, excluir)
        ]
        log.info("%s: %d enlaces, %d relevantes", nombre, len(enlaces), len(relevantes))
        return ResultadoFuente(nombre=nombre, ok=True,
                               nuevos=relevantes, total_relevantes=len(relevantes))

    except Exception as exc:  # incluye RequestException y errores de Playwright
        log.warning("Fallo en fuente '%s': %s", nombre, exc)
        return ResultadoFuente(nombre=nombre, ok=False, error=str(exc))
