"""Punto de entrada: orquesta scraping -> filtrado -> dedup -> correo.

Uso:
    python -m alertas                # ejecución normal (envía correo)
    python -m alertas --dry-run      # no envía correo, imprime el resumen
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from .correo import construye_cuerpo, envia
from .estado import Estado
from .fuentes import procesa_fuente
from .modelo import ResultadoFuente

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alertas")

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.yaml"
ESTADO = RAIZ / "state" / "seen.json"


def cargar_config() -> dict:
    with open(CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ejecutar(dry_run: bool) -> int:
    cfg = cargar_config()
    incluir = cfg["incluir_cualquiera"]
    excluir = cfg.get("excluir", [])
    opciones = cfg.get("opciones", {})

    estado = Estado(ESTADO)
    resultados: list[ResultadoFuente] = []

    for fuente in cfg["fuentes"]:
        rf = procesa_fuente(fuente, incluir, excluir, opciones)
        # Filtra a sólo los NUEVOS respecto al estado previo
        if rf.ok:
            nuevos = [r for r in rf.nuevos if estado.es_nuevo(r.id)]
            for r in nuevos:
                estado.marca(r.id, r.titulo, r.url)
            rf.nuevos = nuevos
        resultados.append(rf)

    _, _, n_novedades = construye_cuerpo(resultados)

    send_always = os.getenv("SEND_ALWAYS", "true").lower() == "true"

    if dry_run:
        texto, _, _ = construye_cuerpo(resultados)
        print("\n" + "=" * 70)
        print(texto)
        print("=" * 70)
        log.info("[dry-run] No se envía correo. Estado NO se modifica.")
        return 0

    if n_novedades == 0 and not send_always:
        log.info("Sin novedades y SEND_ALWAYS=false: no se envía correo.")
        estado.guardar()
        return 0

    remitente = _env("GMAIL_USER")
    password = _env("GMAIL_APP_PASSWORD")
    destinatario = os.getenv("MAIL_TO", remitente)

    envia(remitente, password, destinatario, resultados)
    estado.guardar()  # sólo persistimos tras enviar con éxito
    return 0


def _env(clave: str) -> str:
    valor = os.getenv(clave)
    if not valor:
        log.error("Falta la variable de entorno obligatoria: %s", clave)
        sys.exit(2)
    return valor


def main() -> None:
    parser = argparse.ArgumentParser(description="Alerta de empleo docente")
    parser.add_argument("--dry-run", action="store_true",
                        help="No envía correo ni modifica el estado; sólo imprime.")
    args = parser.parse_args()
    sys.exit(ejecutar(args.dry_run))


if __name__ == "__main__":
    main()
