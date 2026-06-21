# Alerta diaria de empleo docente

Rastrea cada día las convocatorias de **libre disposición, concurso de méritos, comisiones de servicio e interinidades** del Cuerpo de Maestros (especialidades **Inglés, Pedagogía Terapéutica y Psicopedagogía/Orientación**) en **Madrid** y en el **exterior**, y te envía un correo a las 08:00 (hora de Madrid) con las novedades.

Todo corre gratis en **GitHub Actions**. No necesitas servidor.

---

## Cómo funciona

```
GitHub Actions (cron diario)
   └─ python -m alertas
        ├─ Descarga las fuentes configuradas en config.yaml
        ├─ Extrae los enlaces y filtra por palabras clave
        ├─ Compara con state/seen.json (lo ya notificado) -> sólo novedades
        ├─ Envía el correo (SMTP de Gmail)
        └─ Commitea state/seen.json para no repetir mañana
```

- **Filtrado robusto:** filtra por palabras clave sobre el texto de los enlaces (no por la maquetación exacta de cada web), así aguanta mejor los rediseños.
- **Tolerante a fallos:** si una fuente cae, el correo lo indica en el resumen y el resto sigue.
- **Sin duplicados:** una convocatoria sólo se notifica una vez (estado persistido en el repo).
- **Siempre recibes correo:** con novedades o con un "sin cambios hoy" que confirma que el sistema vive.

---

## Puesta en marcha (una sola vez)

### 1. Sube el proyecto a un repositorio de GitHub

Crea un repo **privado** (recomendado) y sube estos archivos. Por línea de comandos:

```bash
git init
git add .
git commit -m "Alerta de empleo docente"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/bolsa-empleo.git
git push -u origin main
```

### 2. Crea una contraseña de aplicación de Gmail

La cuenta que envía el correo necesita una *App Password* (no sirve tu contraseña normal):

1. Activa la **verificación en dos pasos** en tu cuenta Google (requisito).
2. Ve a **https://myaccount.google.com/apppasswords**
3. Crea una contraseña de aplicación (nómbrala p. ej. "Bolsa Empleo"). Copia los **16 caracteres**.

### 3. Configura los Secrets del repositorio

En GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Crea estos tres:

| Secret                 | Valor                                        |
|------------------------|----------------------------------------------|
| `GMAIL_USER`           | El correo que envía (ej. `tucuenta@gmail.com`) |
| `GMAIL_APP_PASSWORD`   | Los 16 caracteres del paso anterior          |
| `MAIL_TO`              | Dónde quieres recibir (`jesusprodriguez@gmail.com`) |

### 4. Activa y prueba

1. Pestaña **Actions** del repo → habilita los workflows si te lo pide.
2. Abre **"Alerta diaria empleo docente"** → botón **Run workflow** (ejecución manual).
3. En ~1 min deberías recibir el primer correo. La primera ejecución detecta TODO lo que ya hay publicado como "novedad"; a partir de ahí sólo te avisa de lo nuevo.

Ya está. Cada día a las 08:00 (Madrid) recibirás el correo automáticamente.

---

## Fuentes con JavaScript (Playwright)

Las fuentes marcadas con `render: js` en `config.yaml` (las del **exterior**, portal del MEFD) se descargan con un navegador headless porque su contenido no está en el HTML inicial. En GitHub Actions ya está todo automatizado (el workflow instala Chromium). Para probarlas **en local** necesitas instalar el navegador una vez:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Las fuentes de Madrid no usan navegador (van por `requests`, más rápido). Si en el futuro alguna fuente nueva carga por JavaScript, basta con añadirle `render: js` en su bloque de `config.yaml`.

---

## Probar en local (opcional)

```bash
pip install -r requirements.txt
python -m playwright install chromium   # sólo si vas a probar las fuentes del exterior

# Sin enviar correo, sólo ver qué detectaría:
python -m alertas --dry-run

# Envío real (necesita las variables de entorno o un fichero .env):
export GMAIL_USER=...
export GMAIL_APP_PASSWORD=...
export MAIL_TO=jesusprodriguez@gmail.com
python -m alertas
```

---

## Personalización

Todo se ajusta en **`config.yaml`** sin tocar el código:

- **`incluir_cualquiera`**: palabras clave que marcan una convocatoria como relevante. Añade/quita especialidades o tipos de proceso.
- **`excluir`**: ruido que quieres descartar.
- **`fuentes`**: añade o cambia URLs a vigilar. Cada fuente sólo necesita `nombre`, `url` y `base`.

Para cambiar la hora, edita el `cron` en `.github/workflows/alerta-diaria.yml`.

---

## Limitaciones que conviene conocer

1. **El cron de GitHub no es exacto.** Se ejecuta "best-effort" y puede retrasarse algunos minutos (incluso una hora en picos de carga). Si necesitas puntualidad estricta, usa un cron externo (p. ej. un servicio que dispare `workflow_dispatch`).

2. **Horario de verano/invierno.** El workflow programa las 06:00 y 07:00 UTC, y un paso comprueba la hora real de Madrid para ejecutar sólo una vez. Así recibes el correo a las 08:00 todo el año sin tocar nada.

3. **Webs que cargan con JavaScript.** El scraper lee el HTML que el servidor entrega. Las páginas de **Madrid** (`comunidad.madrid` y `sede.comunidad.madrid`) sirven el contenido en el HTML, así que se leen con `requests` (rápido). En cambio, el **portal del Ministerio (exterior)** renderiza por JavaScript: esas fuentes están marcadas con `render: js` en `config.yaml` y se leen con **navegador headless (Playwright)** — ver sección siguiente.

4. **El filtrado es por palabras clave.** Puede colarse algún falso positivo o escaparse algo con un título atípico. Ajustar `config.yaml` es la palanca para afinarlo.

---

## Estructura

```
.
├── alertas/
│   ├── __main__.py     # orquestación
│   ├── fuentes.py      # descarga + extracción + filtrado
│   ├── estado.py       # dedup (seen.json)
│   ├── correo.py       # composición y envío SMTP
│   └── modelo.py       # tipos y normalización de texto
├── config.yaml         # keywords y fuentes (edítalo tú)
├── state/seen.json     # convocatorias ya notificadas (lo gestiona el bot)
├── requirements.txt
└── .github/workflows/alerta-diaria.yml
```
