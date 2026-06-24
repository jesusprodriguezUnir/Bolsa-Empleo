"""Genera una vista previa del correo (HTML) sin enviarlo.

Reproduce el pipeline de scraping + filtrado y vuelca el cuerpo HTML que
construye correo.construye_cuerpo() a 'preview_correo.html', para abrirlo en el
navegador y ver cómo quedaría el correo. No envía nada ni toca el estado.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from alertas.correo import construye_cuerpo
from alertas.fuentes import procesa_fuente
from alertas.modelo import ResultadoFuente

RAIZ = Path(__file__).resolve().parent
cfg = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))

incluir = cfg["incluir_cualquiera"]
excluir = cfg.get("excluir", [])
opciones = cfg.get("opciones", {})

resultados: list[ResultadoFuente] = []
for fuente in cfg["fuentes"]:
    resultados.append(procesa_fuente(fuente, incluir, excluir, opciones))

_, cuerpo_html, n = construye_cuerpo(resultados)

# Envolvemos en un HTML mínimo para que el navegador lo renderice bien.
pagina = f"<!doctype html><html><head><meta charset='utf-8'></head><body>{cuerpo_html}</body></html>"
salida = RAIZ / "preview_correo.html"
salida.write_text(pagina, encoding="utf-8")
print(f"Vista previa generada: {salida}  ({n} novedades)")
