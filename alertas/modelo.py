"""Tipos de datos compartidos."""
from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field


def normaliza(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados (para comparar keywords)."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split())


@dataclass(frozen=True)
class Resultado:
    """Una convocatoria/enlace detectado en una fuente."""
    fuente: str
    titulo: str
    url: str

    @property
    def id(self) -> str:
        """Identificador estable para deduplicar (basado en la URL)."""
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]


@dataclass
class ResultadoFuente:
    """Lo obtenido de una fuente en una ejecución."""
    nombre: str
    ok: bool
    nuevos: list[Resultado] = field(default_factory=list)
    total_relevantes: int = 0
    error: str | None = None
