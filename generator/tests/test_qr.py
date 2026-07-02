from estcert import qr


def test_make_qr_ecc_m():
    q = qr.make_qr("hello")
    assert q.error.lower() == "m"


def test_version_is_int():
    q = qr.make_qr("hello")
    assert isinstance(qr.qr_version(q), int)


def test_long_payload_higher_version():
    short = qr.qr_version(qr.make_qr("x"))
    long = qr.qr_version(qr.make_qr("x" * 230))
    assert long > short


def test_png_bytes_are_png():
    q = qr.make_qr("hello")
    data = qr.qr_png_bytes(q, target_pt=90)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
