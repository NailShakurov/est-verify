import fitz
import pytest
from estcert import render, qr

FONT = "assets/DejaVuSans.ttf"


def test_hex_to_rgb():
    assert render.hex_to_rgb("#000000") == (0.0, 0.0, 0.0)
    assert render.hex_to_rgb("#ffffff") == (1.0, 1.0, 1.0)


def test_sanitize_filename():
    assert render.sanitize_filename("Иванов Иван") == "Иванов_Иван"
    assert "/" not in render.sanitize_filename("a/b:c")


def test_fit_fontsize_shrinks():
    font = fitz.Font(fontfile=FONT)
    size = render.fit_fontsize(font, "Очень длинное имя фамилия отчество", 18, 6, 50)
    assert size < 18
    assert size >= 6


def test_render_creates_pdf(tmp_path):
    # шаблон: пустая A4-страница
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    template = tmp_path / "template.pdf"
    doc.save(str(template))
    doc.close()

    q = qr.make_qr("https://est.com.kz/#TT")
    png = qr.qr_png_bytes(q, target_pt=90)
    placement = {
        "fio": {"x": 300, "y": 250, "fontsize": 18, "fio_min_fontsize": 10, "max_width": 260, "color": "#000000"},
        "qr": {"x": 450, "y": 600, "size": 90},
        "verify_label": {"x": 450, "y": 695, "fontsize": 8, "font": "helv"},
    }
    out = tmp_path / "out.pdf"
    render.render_certificate(str(template), str(out), "Иванов Иван", png,
                              placement, FONT, "est.com.kz")
    assert out.exists()
    text = fitz.open(str(out))[0].get_text()
    assert "Иванов Иван" in text
    assert "est.com.kz" in text
