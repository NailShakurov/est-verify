"""Нанесение ФИО, даты, номера, QR и лейбла домена на копию шаблона PDF (PyMuPDF)."""
import io
import re

import fitz

_TEXT_FONTNAME = "estfont"


def sanitize_filename(fio: str) -> str:
    name = fio.strip().replace(" ", "_")
    name = re.sub(r'[/\\:*?"<>|]', "", name)
    name = re.sub(r"_+", "_", name)
    return name


def render_certificate(template_pdf, output_path, fio, qr_png, placement,
                       font_path, domain_label, date_iso, cert_num) -> None:
    doc = fitz.open(template_pdf)
    page = doc[0]
    page.insert_font(fontname=_TEXT_FONTNAME, fontfile=font_path)

    # --- ФИО (кириллический TTF, textbox с центрированием) ---
    fio_cfg = placement["fio"]
    page.insert_textbox(fitz.Rect(*fio_cfg["rect"]), fio,
                        fontname=_TEXT_FONTNAME, fontsize=fio_cfg["fontsize"],
                        color=tuple(fio_cfg["color"]), align=fitz.TEXT_ALIGN_CENTER)

    # --- Дата ---
    date_cfg = placement["date"]
    page.insert_text((date_cfg["x"], date_cfg["y"]), date_iso,
                     fontname=_TEXT_FONTNAME, fontsize=date_cfg["fontsize"],
                     color=tuple(date_cfg["color"]))

    # --- Номер сертификата ---
    num_cfg = placement["cert_num"]
    page.insert_text((num_cfg["x"], num_cfg["y"]), cert_num,
                     fontname=_TEXT_FONTNAME, fontsize=num_cfg["fontsize"],
                     color=tuple(num_cfg["color"]))

    # --- QR ---
    qr_cfg = placement["qr"]
    s = qr_cfg["size"]
    rect = fitz.Rect(qr_cfg["x"], qr_cfg["y"], qr_cfg["x"] + s, qr_cfg["y"] + s)
    page.insert_image(rect, stream=io.BytesIO(qr_png))

    # --- лейбл домена ---
    lbl = placement["verify_label"]
    page.insert_text((lbl["x"], lbl["y"]), domain_label,
                     fontname=_TEXT_FONTNAME, fontsize=lbl["fontsize"],
                     color=tuple(lbl["color"]))

    doc.save(output_path)
    doc.close()
