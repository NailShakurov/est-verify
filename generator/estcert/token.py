"""Контракт токена: payload по спеке, base64url без паддинга, сборка URL."""
import base64

UNIT_SEP = "\x1f"


def b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def build_payload(cert_num: str, fio: str, course: str, date_iso: str) -> bytes:
    fields = [cert_num, fio, course, date_iso]
    for f in fields:
        if UNIT_SEP in f:
            raise ValueError(f"Поле содержит запрещённый разделитель U+001F: {f!r}")
    return UNIT_SEP.join(fields).encode("utf-8")


def build_token(payload: bytes, signature: bytes) -> str:
    return b64url_nopad(payload) + "." + b64url_nopad(signature)


def build_url(domain: str, token: str) -> str:
    return f"https://{domain}/#{token}"
