import fitz
import pytest
from estcert import render, qr

FONT = "assets/DejaVuSans.ttf"


def test_sanitize_filename():
    assert render.sanitize_filename("Иванов Иван") == "Иванов_Иван"
    assert "/" not in render.sanitize_filename("a/b:c")


def test_render_creates_pdf(tmp_path):
    # шаблон: страница того же размера, что и реальный сертификат (1523x1080)
    doc = fitz.open()
    doc.new_page(width=1523, height=1080)
    template = tmp_path / "template.pdf"
    doc.save(str(template))
    doc.close()

    q = qr.make_qr("https://est.com.kz/#TT")
    png = qr.qr_png_bytes(q, target_pt=180)
    placement = {
        "fio": {"rect": [59, 430, 767, 487], "fontsize": 32, "color": [0.1, 0.1, 0.5]},
        "date": {"x": 120, "y": 828, "fontsize": 15, "color": [0, 0, 0]},
        "cert_num": {"x": 400, "y": 960, "fontsize": 13, "color": [0.3, 0.3, 0.3]},
        "qr": {"x": 570, "y": 800, "size": 180},
        "verify_label": {"x": 570, "y": 994, "fontsize": 15, "color": [0.2, 0.2, 0.6]},
    }
    out = tmp_path / "out.pdf"
    render.render_certificate(str(template), str(out), "Иванов Иван", png,
                              placement, FONT, "est.com.kz",
                              "2026-07-02", "001")
    assert out.exists()
    text = fitz.open(str(out))[0].get_text()
    assert "Иванов Иван" in text
    assert "est.com.kz" in text
    assert "2026-07-02" in text
    assert "001" in text
