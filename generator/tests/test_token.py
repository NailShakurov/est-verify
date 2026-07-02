import base64
import pytest
from estcert import token as tk


def test_b64url_nopad_strips_padding():
    assert tk.b64url_nopad(b"\x00\x00") == "AAA"  # без "=="


def test_b64url_roundtrip():
    data = bytes(range(50))
    assert tk.b64url_decode(tk.b64url_nopad(data)) == data


def test_build_payload_positional_order_and_separator():
    p = tk.build_payload("№1", "Иванов Иван", "Курс", "2026-07-02")
    assert p == "№1\x1fИванов Иван\x1fКурс\x1f2026-07-02".encode("utf-8")


def test_build_payload_rejects_separator_in_field():
    with pytest.raises(ValueError):
        tk.build_payload("1", "Иван\x1fов", "Курс", "2026-07-02")


def test_build_token_shape():
    t = tk.build_token(b"payload", b"sig")
    left, right = t.split(".")
    assert tk.b64url_decode(left) == b"payload"
    assert tk.b64url_decode(right) == b"sig"


def test_build_url_uses_fragment():
    assert tk.build_url("est.com.kz", "TT") == "https://est.com.kz/#TT"
