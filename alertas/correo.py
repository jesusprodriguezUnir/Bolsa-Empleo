"""Composición y envío del correo diario por SMTP (Gmail)."""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from .modelo import ResultadoFuente

log = logging.getLogger("alertas.correo")

TZ = ZoneInfo("Europe/Madrid")


def _fecha_es() -> str:
    return datetime.now(TZ).strftime("%d/%m/%Y %H:%M")


# Orden dentro de cada fuente: abiertas antes que próximas; y dentro, las de tu perfil.
_ORDEN_ESTADO = {"abierta": 0, "proxima": 1}


def _ordena(nuevos):
    return sorted(
        nuevos,
        key=lambda r: (_ORDEN_ESTADO.get(r.estado, 2), not r.especialidad, r.titulo.lower()),
    )


def _etiqueta_txt(r) -> str:
    partes = []
    if r.estado == "abierta":
        partes.append("[ABIERTA]")
    elif r.estado == "proxima":
        partes.append("[PRÓXIMA]")
    if r.especialidad:
        partes.append("[TU PERFIL]")
    return " ".join(partes)


def _pill(texto: str, bg: str, fg: str) -> str:
    return (f'<span style="display:inline-block;background:{bg};color:{fg};font-size:11px;'
            f'font-weight:bold;padding:2px 8px;border-radius:10px;margin-right:6px;'
            f'vertical-align:middle">{texto}</span>')


def _item_html(r) -> str:
    pills = ""
    if r.estado == "abierta":
        pills += _pill("ABIERTA", "#eafaef", "#1e8e4e")
    elif r.estado == "proxima":
        pills += _pill("PRÓXIMA", "#fff4e0", "#b8741a")
    if r.especialidad:
        pills += _pill("★ TU PERFIL", "#eef2ff", "#3b4ed8")
    plazo = (f'<div style="color:#666;font-size:13px;margin-top:2px">'
             f'Plazo de presentación: {html.escape(r.plazo)}</div>') if r.plazo else ""
    return (f'<li style="margin-bottom:14px;list-style:none">{pills}'
            f'<a href="{html.escape(r.url)}" style="color:#2b7cff;text-decoration:none;'
            f'font-weight:600">{html.escape(r.titulo)}</a>{plazo}</li>')


def construye_cuerpo(fuentes: list[ResultadoFuente]) -> tuple[str, str, int]:
    """Devuelve (texto_plano, html, num_novedades)."""
    total_nuevos = sum(len(f.nuevos) for f in fuentes)
    fallos = [f for f in fuentes if not f.ok]

    # ---- Texto plano ----
    tp: list[str] = [f"Alertas de empleo docente — {_fecha_es()}", ""]
    if total_nuevos == 0:
        tp.append("Sin novedades hoy. No hay convocatorias nuevas que cumplan tus criterios.")
    else:
        tp.append(f"{total_nuevos} novedad(es) detectada(s):")
    tp.append("")
    for f in fuentes:
        if f.nuevos:
            tp.append(f"## {f.nombre}")
            for r in _ordena(f.nuevos):
                etq = _etiqueta_txt(r)
                tp.append(f"  - {etq + ' ' if etq else ''}{r.titulo}")
                if r.plazo:
                    tp.append(f"    Plazo de presentación: {r.plazo}")
                tp.append(f"    {r.url}")
            tp.append("")
    if fallos:
        tp.append("Fuentes con error (revisar):")
        for f in fallos:
            tp.append(f"  - {f.nombre}: {f.error}")
    texto = "\n".join(tp)

    # ---- HTML ----
    h: list[str] = [
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;'
        'margin:auto;color:#1a1a1a">',
        f'<h2 style="margin:0 0 4px">Alertas de empleo docente</h2>',
        f'<p style="color:#666;margin:0 0 20px">{_fecha_es()}</p>',
    ]
    if total_nuevos == 0:
        h.append(
            '<p style="background:#eef6ff;border-left:4px solid #2b7cff;padding:12px 16px">'
            'Sin novedades hoy. No hay convocatorias nuevas que cumplan tus criterios.</p>')
    else:
        h.append(
            f'<p style="background:#eafaef;border-left:4px solid #2ecc71;padding:12px 16px">'
            f'<b>{total_nuevos} novedad(es)</b> detectada(s) hoy.</p>')
        for f in fuentes:
            if not f.nuevos:
                continue
            h.append(f'<h3 style="margin:24px 0 8px;border-bottom:1px solid #eee;'
                     f'padding-bottom:4px">{html.escape(f.nombre)}</h3>'
                     f'<ul style="padding-left:0">')
            for r in _ordena(f.nuevos):
                h.append(_item_html(r))
            h.append("</ul>")

    # Resumen por fuente (siempre)
    h.append('<h3 style="margin:24px 0 8px;color:#666">Resumen de fuentes</h3>'
             '<table style="border-collapse:collapse;width:100%;font-size:13px">')
    for f in fuentes:
        estado = (f'<span style="color:#2ecc71">OK</span>' if f.ok
                  else f'<span style="color:#e74c3c">ERROR</span>')
        detalle = (f"{f.total_relevantes} relevante(s), {len(f.nuevos)} nuevo(s)"
                   if f.ok else html.escape(f.error or ""))
        h.append(
            f'<tr style="border-bottom:1px solid #f0f0f0">'
            f'<td style="padding:6px 8px">{html.escape(f.nombre)}</td>'
            f'<td style="padding:6px 8px">{estado}</td>'
            f'<td style="padding:6px 8px;color:#555">{detalle}</td></tr>')
    h.append("</table>")
    h.append('<p style="color:#999;font-size:12px;margin-top:24px">'
             'Generado automáticamente por tu alerta de Bolsa de Empleo.</p></div>')

    return texto, "\n".join(h), total_nuevos


def envia(remitente: str, password: str, destinatario: str,
          fuentes: list[ResultadoFuente], asunto_extra: str = "") -> None:
    texto, cuerpo_html, n = construye_cuerpo(fuentes)

    if n > 0:
        asunto = f"🔔 {n} novedad(es) en empleo docente — {datetime.now(TZ):%d/%m}"
    else:
        asunto = f"Empleo docente: sin novedades — {datetime.now(TZ):%d/%m}"
    if asunto_extra:
        asunto = f"{asunto_extra} {asunto}"

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario
    msg.set_content(texto)
    msg.add_alternative(cuerpo_html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as smtp:
        smtp.login(remitente, password)
        smtp.send_message(msg)
    log.info("Correo enviado a %s (%d novedades)", destinatario, n)
