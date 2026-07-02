"""Нанесение ФИО, QR и лейбла домена на копию шаблона PDF (PyMuPDF)."""
import io
import re

import fitz

_FIO_FONTNAME = "estfio"


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def sanitize_filename(fio: str) -> str:
    name = fio.strip().replace(" ", "_")
    name = re.sub(r'[/\\:*?"<>|]', "", name)
    name = re.sub(r"_+", "_", name)
    return name


def fit_fontsize(font, text, fontsize, min_fontsize, max_width) -> float:
    size = float(fontsize)
    while size > min_fontsize and font.text_length(text, size) > max_width:
        size -= 0.5
    return max(size, float(min_fontsize))


def render_certificate(template_pdf, output_path, fio, qr_png, placement,
                       font_file, domain_label) -> None:
    doc = fitz.open(template_pdf)
    page = doc[0]

    # --- ФИО (кириллический TTF, центр по x, авто-fit) ---
    fio_cfg = placement["fio"]
    font = fitz.Font(fontfile=font_file)
    page.insert_font(fontname=_FIO_FONTNAME, fontfile=font_file)
    size = fit_fontsize(font, fio, fio_cfg["fontsize"],
                        fio_cfg.get("fio_min_fontsize", fio_cfg["fontsize"]),
                        fio_cfg.get("max_width", float("inf")))
    tw = font.text_length(fio, size)
    x = fio_cfg["x"] - tw / 2.0
    page.insert_text((x, fio_cfg["y"]), fio, fontname=_FIO_FONTNAME,
                     fontsize=size, color=hex_to_rgb(fio_cfg.get("color", "#000000")))

    # --- QR ---
    qr_cfg = placement["qr"]
    s = qr_cfg["size"]
    rect = fitz.Rect(qr_cfg["x"], qr_cfg["y"], qr_cfg["x"] + s, qr_cfg["y"] + s)
    page.insert_image(rect, stream=io.BytesIO(qr_png))

    # --- лейбл домена (латиница, helv) ---
    lbl = placement["verify_label"]
    page.insert_text((lbl["x"], lbl["y"]), domain_label,
                     fontname=lbl.get("font", "helv"), fontsize=lbl["fontsize"],
                     color=(0, 0, 0))

    doc.save(output_path)
    doc.close()
