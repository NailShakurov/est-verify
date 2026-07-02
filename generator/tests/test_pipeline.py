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
        "font_path": "assets/DejaVuSans.ttf",
        "placement": {
            "fio": {"rect": [59, 430, 767, 487], "fontsize": 32, "color": [0.1, 0.1, 0.5]},
            "date": {"x": 120, "y": 828, "fontsize": 15, "color": [0, 0, 0]},
            "cert_num": {"x": 400, "y": 960, "fontsize": 13, "color": [0.3, 0.3, 0.3]},
            "qr": {"x": 570, "y": 800, "size": 180},
            "verify_label": {"x": 570, "y": 994, "fontsize": 15, "color": [0.2, 0.2, 0.6]},
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
