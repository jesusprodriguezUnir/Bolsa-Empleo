"""Tipos de datos compartidos."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field


def normaliza(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados (para comparar keywords)."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split())


def contiene(texto_norm: str, keyword: str) -> bool:
    """Match por PREFIJO de palabra, token a token, sobre texto YA normalizado.

    Cada palabra de la keyword admite sufijos (plurales/derivados) pero debe empezar
    en límite de palabra:
      - 'interino'             casa 'interinos', 'interinidad'
      - 'comision de servicio' casa 'comisiones de servicio'
    pero 'pt' NO casa dentro de 'apto' (no hay límite de palabra antes).
    """
    tokens = normaliza(keyword).split()
    patron = r"\b" + r"\w*\s+".join(re.escape(t) for t in tokens) + r"\w*"
    return re.search(patron, texto_norm) is not None


@dataclass(frozen=True)
class Resultado:
    """Una convocatoria/enlace detectado en una fuente.

    Campos extra (opcionales) que rellenan las fuentes con vigencia (comisiones):
      - estado: "abierta" | "proxima" | "caducada" | None (fuentes genéricas)
      - plazo:  texto del plazo de presentación, p. ej. "del 23 al 29 de junio de 2026"
      - especialidad: True si el texto casa con inglés / PT / psicopedagogía / orientación
      - dedup_key: clave alternativa para deduplicar. Si se informa, el `id` se basa en
        ella en lugar de solo en la URL. Las comisiones la usan para incluir el estado,
        de modo que una convocatoria "proxima" se vuelve a notificar cuando pasa a
        "abierta" (misma URL, distinto estado -> evento nuevo).
    """
    fuente: str
    titulo: str
    url: str
    estado: str | None = None
    plazo: str | None = None
    especialidad: bool = False
    dedup_key: str | None = None

    @property
    def id(self) -> str:
        """Identificador estable para deduplicar (URL, o `dedup_key` si se informa)."""
        base = self.dedup_key if self.dedup_key else self.url
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


@dataclass
class ResultadoFuente:
    """Lo obtenido de una fuente en una ejecución."""
    nombre: str
    ok: bool
    nuevos: list[Resultado] = field(default_factory=list)
    total_relevantes: int = 0
    error: str | None = None
