"""
report_generator.py — Genera el informe PDF de verificación ISO 8253-1
usando ReportLab. Incluye: encabezado, datos del ensayo, tabla de resultados
por banda de octava, veredicto, condiciones y bloque de firmas.
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from database import ISO_LIMITS

W, H = A4  # 595.27 x 841.89 pt

# ── Colores institucionales ──────────────────────────────────
NAVY  = colors.HexColor("#1B3A5C")
BLUE  = colors.HexColor("#2E75B6")
GREEN = colors.HexColor("#1E6B35")
RED   = colors.HexColor("#B52020")
LGRAY = colors.HexColor("#EBF0FA")
DGRAY = colors.HexColor("#D9E2F3")

def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Title2",   parent=s["Title"],  fontSize=16,  textColor=NAVY,  spaceAfter=4))
    s.add(ParagraphStyle("Sub",      parent=s["Normal"], fontSize=9,   textColor=BLUE,  spaceAfter=2))
    s.add(ParagraphStyle("Body",     parent=s["Normal"], fontSize=9,   spaceAfter=3,    leading=13))
    s.add(ParagraphStyle("Small",    parent=s["Normal"], fontSize=7,   textColor=colors.grey))
    s.add(ParagraphStyle("Section",  parent=s["Normal"], fontSize=10,  textColor=NAVY, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4))
    s.add(ParagraphStyle("Verdict",  parent=s["Normal"], fontSize=18,  fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=6))
    s.add(ParagraphStyle("CellHdr",  parent=s["Normal"], fontSize=8,   fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER))
    s.add(ParagraphStyle("CellBody", parent=s["Normal"], fontSize=8,   alignment=TA_CENTER))
    return s

def _hr(): return HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=6, spaceBefore=2)

def _field_table(pairs: list[tuple], col_w=(3*cm, 6.5*cm, 3*cm, 6.5*cm)) -> Table:
    """Genera una tabla de 4 columnas: etiqueta | valor | etiqueta | valor"""
    data, row = [], []
    for i, (label, value) in enumerate(pairs):
        row += [Paragraph(f"<b>{label}:</b>", _styles()["Body"]),
                Paragraph(str(value or "—"), _styles()["Body"])]
        if len(row) == 4:
            data.append(row); row = []
    if row:
        data.append(row + ["", ""])
    t = Table(data, colWidths=col_w, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID",      (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, LGRAY]),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
    ]))
    return t

def generate_pdf(session: dict, averages: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.8*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title="Informe ISO 8253-1",
    )
    st = _styles()
    story = []
    bandas = [125, 250, 500, 1000, 2000, 4000, 8000]

    # ── 1. ENCABEZADO ────────────────────────────────────────
    story.append(Paragraph(
        f"<b>INFORME DE VERIFICACIÓN DE RUIDO AMBIENTE</b><br/>"
        f"<font size='10' color='#2E75B6'>Norma ISO 8253-1 : 2010 — Audiometría de tonos puros por vía aérea</font>",
        st["Title2"]))
    story.append(_hr())

    ts = session.get("started_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    inst = session.get("institucion", "") or "—"
    nro  = session.get("id", "—")
    story.append(_field_table([
        ("Nro. de Informe",  f"ISO-{nro:04d}" if isinstance(nro,int) else nro),
        ("Fecha de ensayo",  ts[:16].replace("T"," ")),
        ("Institución",      inst),
        ("Sala / Consultorio", session.get("sala","") or "—"),
        ("Dirección",         session.get("direccion","") or "—"),
        ("",                  ""),
    ], col_w=(2.8*cm, 6.8*cm, 2.8*cm, 6.8*cm)))
    story.append(Spacer(1, 0.3*cm))

    # ── 2. PERSONAL ACTUANTE ─────────────────────────────────
    story.append(Paragraph("Personal actuante", st["Section"]))
    story.append(_field_table([
        ("Fonoaudiólogo",   session.get("fonoaudiologo","") or "—"),
        ("Mat. Fono.",       session.get("mat_fono","")      or "—"),
        ("Bioingeniero",     session.get("bioingeniero","")  or "—"),
        ("Mat. Bio.",        session.get("mat_bio","")       or "—"),
    ]))
    story.append(Spacer(1, 0.3*cm))

    # ── 3. EQUIPAMIENTO ──────────────────────────────────────
    story.append(Paragraph("Equipamiento utilizado", st["Section"]))
    story.append(_field_table([
        ("Analizador",   "ESP32 + INMP441 MEMS I2S  ·  Soft. UNER 2026"),
        ("S/N equipo",   session.get("equipo_sn","") or "—"),
        ("Calibrador",   "Pistonófono 94 dB SPL @ 1 kHz"),
        ("S/N / Cert.",  session.get("pistonofono","") or "—"),
    ]))
    story.append(Spacer(1, 0.3*cm))

    # ── 4. CONDICIONES AMBIENTALES ───────────────────────────
    story.append(Paragraph("Condiciones durante la medición", st["Section"]))
    story.append(_field_table([
        ("Temperatura", f"{session.get('temperatura','—')} °C"),
        ("Humedad rel.", f"{session.get('humedad','—')} %"),
        ("Observaciones", session.get("observaciones","") or "Ninguna"),
        ("", ""),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # ── 5. TABLA DE RESULTADOS ───────────────────────────────
    story.append(Paragraph("Resultados de medición por banda de octava", st["Section"]))

    header = [Paragraph(t, st["CellHdr"]) for t in
              ["Banda\n(Hz)", "Medido\n(dB SPL)", "Límite ISO\n(dB SPL)",
               "Margen\n(dB)", "Estado"]]
    rows = [header]
    all_ok = True
    for fc in bandas:
        val    = averages.get(fc, None)
        limite = ISO_LIMITS[fc]
        if val is None:
            rows.append([Paragraph(str(fc), st["CellBody"])] + [Paragraph("—", st["CellBody"])]*4)
            continue
        margen = limite - val
        ok     = margen >= 0
        if not ok: all_ok = False
        color  = GREEN if ok else RED
        estado = Paragraph(f'<font color="{"#1E6B35" if ok else "#B52020"}"><b>{"CUMPLE ✔" if ok else "NO CUMPLE ✘"}</b></font>', st["CellBody"])
        rows.append([
            Paragraph(str(fc), st["CellBody"]),
            Paragraph(f"{val:.1f}", st["CellBody"]),
            Paragraph(str(limite), st["CellBody"]),
            Paragraph(f'<font color="{"#1E6B35" if ok else "#B52020"}">{"+" if ok else ""}{margen:.1f}</font>', st["CellBody"]),
            estado,
        ])

    col_w = [2.5*cm, 3*cm, 3*cm, 2.8*cm, 7.9*cm]
    tbl = Table(rows, colWidths=col_w, hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), NAVY),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, LGRAY]),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── 6. VEREDICTO GLOBAL ──────────────────────────────────
    if all_ok:
        verdict_text = '<font color="#1E6B35">✔  CABINA APTA PARA AUDIOMETRÍAS (ISO 8253-1)</font>'
        box_color    = colors.HexColor("#D5F0DE")
    else:
        verdict_text = '<font color="#B52020">✘  CABINA NO APTA — No realizar audiometrías</font>'
        box_color    = colors.HexColor("#FAD9DE")

    verdict_p = Paragraph(verdict_text, st["Verdict"])
    verdict_tbl = Table([[verdict_p]], colWidths=[19.2*cm])
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), box_color),
        ("BOX",           (0,0), (-1,-1), 1.5, NAVY),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(verdict_tbl)
    story.append(Spacer(1, 0.6*cm))

    # ── 7. BLOQUE DE FIRMAS ──────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Conformidad y Firmas", st["Section"]))

    firma_fono = [
        [Paragraph("<b>Fonoaudiólogo/a responsable</b>", st["Body"])],
        [Paragraph(" " * 60, st["Body"])],
        [Paragraph(" " * 60, st["Body"])],
        [Paragraph(f"Nombre: {session.get('fonoaudiologo','') or '___________________________'}", st["Body"])],
        [Paragraph(f"Mat. Prov./Nac.: {session.get('mat_fono','') or '_____________'}", st["Body"])],
        [Paragraph("Firma y sello:", st["Body"])],
        [Paragraph("\n\n\n", st["Body"])],
    ]
    firma_bio = [
        [Paragraph("<b>Bioingeniero/a responsable</b>", st["Body"])],
        [Paragraph(" " * 60, st["Body"])],
        [Paragraph(" " * 60, st["Body"])],
        [Paragraph(f"Nombre: {session.get('bioingeniero','') or '___________________________'}", st["Body"])],
        [Paragraph(f"Mat. Prov./Nac.: {session.get('mat_bio','') or '_____________'}", st["Body"])],
        [Paragraph("Firma y sello:", st["Body"])],
        [Paragraph("\n\n\n", st["Body"])],
    ]

    tf = Table([[Table(firma_fono,colWidths=[9*cm]), Table(firma_bio,colWidths=[9*cm])]],
               colWidths=[9.5*cm, 9.7*cm])
    tf.setStyle(TableStyle([
        ("BOX",   (0,0), (0,0), 0.5, colors.grey),
        ("BOX",   (1,0), (1,0), 0.5, colors.grey),
        ("TOPPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(tf)

    # ── 8. PIE DE PÁGINA ─────────────────────────────────────
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Documento generado automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M')} "
        f"por el Sistema de Verificación ISO 8253-1 — UNER 2026. "
        f"Los valores tienen valor metrológico solo si el equipo fue calibrado con pistonófono certificado.",
        st["Small"]))

    doc.build(story)
    return buf.getvalue()
