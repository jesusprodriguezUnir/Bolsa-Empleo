# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Bot que rastrea convocatorias de empleo docente (Cuerpo de Maestros: Inglés, PT, Psicopedagogía/Orientación) en Madrid y en el exterior, y envía un correo diario a las 08:00 (Madrid) con las novedades. Corre íntegramente en GitHub Actions (cron); no hay servidor. Toda la interfaz, comentarios y mensajes están en español.

## Comandos

```bash
pip install -r requirements.txt
python -m playwright install chromium   # solo para fuentes render:js (exterior/MEFD)

python -m alertas --dry-run             # scraping + filtrado, imprime resumen, NO envía ni toca el estado
python -m alertas                       # ejecución real: requiere GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO
```

No hay tests, linter ni build. La verificación es `--dry-run`. Para probar el envío real en local, copia `.env.example` a `.env` (no se carga solo: hay que exportar las variables o cargarlas a mano).

## Arquitectura

Paquete `alertas/` ejecutado como módulo (`python -m alertas`). Pipeline en [`__main__.py`](alertas/__main__.py) `ejecutar()`:

1. Lee `config.yaml` (keywords + fuentes).
2. Por cada fuente → [`fuentes.py`](alertas/fuentes.py) `procesa_fuente()`: descarga, extrae todos los `<a>` con texto significativo y filtra por keywords.
3. Deduplica contra `state/seen.json` vía [`estado.py`](alertas/estado.py) (`Estado`).
4. Compone y envía el correo → [`correo.py`](alertas/correo.py).
5. Persiste `state/seen.json` **solo tras enviar con éxito** (en GitHub Actions el workflow commitea ese fichero).

### Decisiones de diseño que importan

- **Dedup por hash de URL.** `Resultado.id` ([`modelo.py`](alertas/modelo.py)) es `sha256(url)[:16]`. La identidad de una convocatoria es su URL: si una fuente cambia la URL de un enlace, se notifica como novedad. El estado es un histórico acumulativo que nunca se purga.

- **Filtrado por keywords sobre el texto del enlace, no por la maquetación.** `es_relevante()` exige ≥1 palabra de `incluir_cualquiera` y ninguna de `excluir`. El match (`_contiene` en `fuentes.py`) es por **prefijo de palabra token a token** con regex `\bword\w*`: `interino` casa `interinos`/`interinidad`, pero evita falsos positivos dentro de otras palabras. Todo se compara normalizado (minúsculas, sin acentos) vía `normaliza()`.

- **Dos vías de descarga según la fuente.** `requests` por defecto (Madrid sirve HTML en servidor); navegador headless Playwright cuando la fuente lleva `render: js` en `config.yaml` (portal MEFD/exterior, que renderiza por JavaScript). Playwright se importa de forma **perezosa** dentro de `_descarga_playwright` para no exigirlo cuando no hace falta.

- **Tolerante a fallos.** Si una fuente lanza excepción, se captura y se devuelve `ResultadoFuente(ok=False, error=...)`; el resto sigue y el correo lista las fuentes con error.

- **Siempre se envía correo** (`SEND_ALWAYS=true` por defecto): con novedades o con un "sin cambios hoy" que confirma que el sistema vive. Con `SEND_ALWAYS=false` y cero novedades no se envía.

### Configuración

`config.yaml` es la palanca principal y se edita sin tocar código: `incluir_cualquiera`, `excluir`, lista de `fuentes` (cada una `nombre`/`tipo`/`url`/`base`, opcional `render: js`) y `opciones` (`min_long_titulo`, `timeout`). Para añadir una fuente que carga por JS, basta con `render: js`.

### Despliegue (GitHub Actions)

[`.github/workflows/alerta-diaria.yml`](.github/workflows/alerta-diaria.yml) corre en dos crons (06:00 y 07:00 UTC) y un paso decide si la hora local de Madrid es las 08:00 para ejecutar **una sola vez** todo el año pese al cambio horario CET/CEST. Necesita `permissions: contents: write` para commitear `state/seen.json`. Credenciales como repository secrets: `GMAIL_USER`, `GMAIL_APP_PASSWORD` (App Password de 16 caracteres, no la contraseña normal), `MAIL_TO`. El correo se envía por SMTP_SSL de Gmail (puerto 465).
