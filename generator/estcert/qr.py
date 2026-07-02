"""Генерация QR через segno (уровень коррекции M) и рендер в PNG."""
import io

import segno


def make_qr(data: str) -> segno.QRCode:
    return segno.make(data, error="m")


def qr_version(qrcode) -> int:
    v = qrcode.version
    # у микро-QR version — строка вида 'M1'..'M4'; для обычных QR это int
    return v if isinstance(v, int) else int(str(v).lstrip("M"))


def qr_png_bytes(qrcode, target_pt: float, dpi: int = 300) -> bytes:
    # целевой физический размер в дюймах -> пиксели; scale = пиксели / число модулей
    px = max(1, int(round(target_pt / 72.0 * dpi)))
    modules = qrcode.symbol_size(scale=1, border=1)[0]
    scale = max(1, round(px / modules))
    buf = io.BytesIO()
    qrcode.save(buf, kind="png", scale=scale, border=1)
    return buf.getvalue()
