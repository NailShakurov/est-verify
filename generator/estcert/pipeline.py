"""Пайплайн одного сертификата: token -> QR -> PDF."""
import os
import warnings

from estcert import qr as qrmod
from estcert import render
from estcert import token as tk


def course_for(config: dict, compact: bool) -> str:
    return config["course_code"] if compact else config["course_name"]


def build_token_for_row(sk, config: dict, row: dict, compact: bool):
    course = course_for(config, compact)
    payload = tk.build_payload(row["number"], row["fio"], course, row["date_iso"])
    from estcert import keys
    signature = keys.sign(sk, payload)
    token = tk.build_token(payload, signature)
    url = tk.build_url(config["domain"], token)
    q = qrmod.make_qr(url)
    return token, url, qrmod.qr_version(q)


def generate_one(sk, config: dict, row: dict, compact: bool) -> dict:
    course = course_for(config, compact)
    payload = tk.build_payload(row["number"], row["fio"], course, row["date_iso"])
    from estcert import keys
    signature = keys.sign(sk, payload)
    token = tk.build_token(payload, signature)
    url = tk.build_url(config["domain"], token)

    q = qrmod.make_qr(url)
    version = qrmod.qr_version(q)
    if version > 10:
        warnings.warn(f"QR версии {version} > 10 для {row['number']} — проверьте читаемость")

    png = qrmod.qr_png_bytes(q, target_pt=config["placement"]["qr"]["size"])

    os.makedirs(config["output_dir"], exist_ok=True)
    fname = f"{row['number']}_{render.sanitize_filename(row['fio'])}.pdf"
    out_path = os.path.join(config["output_dir"], fname)
    render.render_certificate(
        config["template_pdf"], out_path, row["fio"], png,
        config["placement"], config["font_file"], config["domain"],
    )
    return {"path": out_path, "qr_version": version, "url": url}
