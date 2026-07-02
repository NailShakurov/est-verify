import base64
import fitz
import nacl.signing
import pytest
from estcert import pipeline, keys, token as tk


@pytest.fixture
def setup(tmp_path):
    # шаблон
    doc = fitz.open(); doc.new_page(width=595, height=842)
    template = tmp_path / "template.pdf"; doc.save(str(template)); doc.close()
    # ключи
    priv = tmp_path / "priv.key"; pub = tmp_path / "pub.key"
    keys.genkey(str(priv), str(pub))
    sk = keys.load_signing_key(str(priv))
    pubkey = keys.load_public_key(str(pub))
    config = {
        "domain": "est.com.kz",
        "course_name": "Евразийская школа трекинга",
        "course_code": "E",
        "template_pdf": str(template),
        "output_dir": str(tmp_path / "out"),
        "font_file": "assets/DejaVuSans.ttf",
        "placement": {
            "fio": {"x": 300, "y": 250, "fontsize": 18, "fio_min_fontsize": 10, "max_width": 260, "color": "#000000"},
            "qr": {"x": 450, "y": 600, "size": 90},
            "verify_label": {"x": 450, "y": 695, "fontsize": 8, "font": "helv"},
        },
    }
    row = {"number": "001", "fio": "Иванов Иван", "date_iso": "2026-07-02", "row": 2}
    return sk, pubkey, config, row


def test_course_for():
    cfg = {"course_name": "Полное", "course_code": "E"}
    assert pipeline.course_for(cfg, False) == "Полное"
    assert pipeline.course_for(cfg, True) == "E"


def test_token_verifies_with_pubkey(setup):
    sk, pubkey, config, row = setup
    token, url, ver = pipeline.build_token_for_row(sk, config, row, compact=False)
    payload_b64, sig_b64 = token.split(".")
    payload = tk.b64url_decode(payload_b64)
    sig = tk.b64url_decode(sig_b64)
    nacl.signing.VerifyKey(pubkey).verify(payload, sig)  # не бросает
    assert payload.decode("utf-8").split("\x1f") == [
        "001", "Иванов Иван", "Евразийская школа трекинга", "2026-07-02"]


def test_generate_one_writes_pdf(setup):
    sk, pubkey, config, row = setup
    res = pipeline.generate_one(sk, config, row, compact=False)
    assert res["path"].endswith("001_Иванов_Иван.pdf")
    import os
    assert os.path.exists(res["path"])
