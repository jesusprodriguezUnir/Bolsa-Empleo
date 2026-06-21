"""Persistencia del estado: qué convocatorias ya se han notificado (dedup)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("alertas.estado")


class Estado:
    """Guarda los IDs ya notificados en un JSON que se commitea al repo."""

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.vistos: dict[str, dict] = {}
        self._cargar()

    def _cargar(self) -> None:
        if self.ruta.exists():
            try:
                data = json.loads(self.ruta.read_text(encoding="utf-8"))
                self.vistos = data.get("vistos", {})
                log.info("Estado cargado: %d entradas previas", len(self.vistos))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("No se pudo leer el estado (%s). Empiezo vacío.", exc)
        else:
            log.info("Sin estado previo: primera ejecución.")

    def es_nuevo(self, id_: str) -> bool:
        return id_ not in self.vistos

    def marca(self, id_: str, titulo: str, url: str) -> None:
        self.vistos[id_] = {
            "titulo": titulo,
            "url": url,
            "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        payload = {"actualizado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "vistos": self.vistos}
        self.ruta.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Estado guardado: %d entradas", len(self.vistos))
