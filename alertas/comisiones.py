"""Extractor con vigencia para convocatorias tipo "Comisión de servicio".

A diferencia del extractor genérico de `fuentes.py` (que mira solo el texto de cada
`<a>`), aquí necesitamos contexto de BLOQUE: el título de la oferta, su PDF, y la línea
"Plazo de presentación de solicitudes del X al Y de MES de AÑO" que aparece como texto
hermano, no dentro del enlace.

Estrategia (robusta a la maquetación, sea lista o blockquote):

1. Se recorre el documento en orden y se construye un flujo de eventos
   (texto / enlace), sin recursar dentro de los `<a>`.
2. Cada enlace cuyo texto empieza por "oferta" abre una nueva convocatoria; el texto y
   los enlaces siguientes (solicitud, formulario) se acumulan en ella hasta la próxima
   oferta.
3. De ese texto acumulado se extrae el plazo y se clasifica la vigencia respecto a hoy.

Las convocatorias del histórico (acordeón "Convocatorias anteriores") empiezan también
por "Oferta de" pero NO llevan línea de plazo, así que quedan descartadas de forma
natural: solo sobreviven las que tienen un plazo parseable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

from .modelo import contiene, normaliza

# Especialidades del usuario: si el texto de la convocatoria casa con alguna, se destaca.
ESPECIALIDADES = (
    "ingles",
    "pedagogia terapeutica",
    "audicion y lenguaje",
    "psicopedagogia",
    "orientacion educativa",
    "orientacion",
)

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# "del 23 [de junio] al 29 de junio [de 2026]"  -> d1, m1?, d2, m2, año?
_PLAZO = re.compile(
    r"del\s+(\d{1,2})(?:\s+de\s+([a-zñ]+))?\s+al\s+(\d{1,2})\s+de\s+([a-zñ]+)"
    r"(?:\s+de\s+(\d{4}))?"
)


@dataclass
class Convocatoria:
    titulo: str
    url: str
    estado: str            # "abierta" | "proxima" | "caducada"
    plazo: str             # texto legible: "del 23 al 29 de junio de 2026"
    especialidad: bool


def parse_plazo(texto_norm: str, anio_defecto: int) -> tuple[date, date] | None:
    """Extrae (fecha_inicio, fecha_fin) de un texto normalizado. None si no hay plazo."""
    m = _PLAZO.search(texto_norm)
    if not m:
        return None
    d1, m1, d2, m2, anio = m.groups()
    mes_fin = _MESES.get(m2 or "")
    mes_ini = _MESES.get(m1 or "") or mes_fin  # si no se indica, comparte mes con el fin
    if not mes_fin or not mes_ini:
        return None
    anio = int(anio) if anio else anio_defecto
    try:
        ini = date(anio, mes_ini, int(d1))
        fin = date(anio, mes_fin, int(d2))
    except ValueError:
        return None
    # Si el inicio cae después del fin (cruce de año en plazos a caballo de diciembre),
    # el inicio pertenece al año anterior.
    if ini > fin:
        try:
            ini = date(anio - 1, mes_ini, int(d1))
        except ValueError:
            return None
    return ini, fin


def clasifica(ini: date, fin: date, hoy: date) -> str:
    if hoy < ini:
        return "proxima"
    if ini <= hoy <= fin:
        return "abierta"
    return "caducada"


def _es_oferta(titulo_norm: str) -> bool:
    """Un enlace abre convocatoria si su texto empieza por 'oferta'."""
    return titulo_norm.startswith("oferta")


def _eventos(node: Tag):
    """Genera ('text', str) y ('link', titulo, href) en orden de documento.

    No recursa dentro de los `<a>`: cada enlace se emite como una unidad.
    """
    for child in node.children:
        if isinstance(child, NavigableString):
            txt = str(child).strip()
            if txt:
                yield ("text", txt)
        elif isinstance(child, Tag):
            if child.name in ("script", "style"):
                continue
            if child.name == "a" and child.get("href"):
                titulo = " ".join(child.get_text(" ", strip=True).split())
                if titulo:
                    yield ("link", titulo, child["href"].strip())
            else:
                yield from _eventos(child)


def _tiene_especialidad(texto_norm: str) -> bool:
    return any(contiene(texto_norm, kw) for kw in ESPECIALIDADES)


def extrae_convocatorias(html: str, base: str, hoy: date) -> list[Convocatoria]:
    """Devuelve las convocatorias con plazo detectadas en la página."""
    soup = BeautifulSoup(html, "html.parser")
    raiz = soup.body or soup

    convs: list[dict] = []
    actual: dict | None = None
    for ev in _eventos(raiz):
        if ev[0] == "link":
            _, titulo, href = ev
            if _es_oferta(normaliza(titulo)):
                actual = {"titulo": titulo, "url": urljoin(base, href), "buf": [titulo]}
                convs.append(actual)
            elif actual is not None:
                actual["buf"].append(titulo)  # solicitud / formulario: contexto
        elif ev[0] == "text" and actual is not None:
            actual["buf"].append(ev[1])

    salida: list[Convocatoria] = []
    vistas: set[str] = set()
    for c in convs:
        texto_norm = normaliza(" ".join(c["buf"]))
        rango = parse_plazo(texto_norm, anio_defecto=hoy.year)
        if not rango:
            continue  # descarta histórico y enlaces sin plazo
        ini, fin = rango
        if c["url"] in vistas:
            continue
        vistas.add(c["url"])
        salida.append(Convocatoria(
            titulo=c["titulo"],
            url=c["url"],
            estado=clasifica(ini, fin, hoy),
            plazo=_plazo_legible(ini, fin),
            especialidad=_tiene_especialidad(texto_norm),
        ))
    return salida


_MES_NOMBRE = {v: k for k, v in _MESES.items() if k != "setiembre"}


def _plazo_legible(ini: date, fin: date) -> str:
    if ini.month == fin.month and ini.year == fin.year:
        return f"del {ini.day} al {fin.day} de {_MES_NOMBRE[fin.month]} de {fin.year}"
    return (f"del {ini.day} de {_MES_NOMBRE[ini.month]} "
            f"al {fin.day} de {_MES_NOMBRE[fin.month]} de {fin.year}")
