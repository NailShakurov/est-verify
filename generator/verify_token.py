#!/usr/bin/env python3
"""Приёмочная проверка токена: декод payload + verify подписи публичным ключом.

Использование:
  python verify_token.py "<token или URL>" --public ./keys/ed25519_public.key
"""
import argparse
import sys

import nacl.exceptions
import nacl.signing

from estcert import keys
from estcert import token as tk


def verify(token_or_url: str, public_path: str) -> int:
    token = token_or_url.split("#", 1)[1] if "#" in token_or_url else token_or_url
    try:
        payload_b64, sig_b64 = token.split(".")
    except ValueError:
        print("Некорректный формат токена (нет '.')", file=sys.stderr)
        return 1
    payload = tk.b64url_decode(payload_b64)
    sig = tk.b64url_decode(sig_b64)
    pubkey = keys.load_public_key(public_path)

    fields = payload.decode("utf-8").split(tk.UNIT_SEP)
    if len(fields) != 4:
        print(f"Ожидалось 4 поля, получено {len(fields)}", file=sys.stderr)
        return 1
    cert_num, fio, course, date_iso = fields
    print(f"№ сертификата: {cert_num}")
    print(f"ФИО:           {fio}")
    print(f"Курс:          {course}")
    print(f"Дата выдачи:   {date_iso}")

    try:
        nacl.signing.VerifyKey(pubkey).verify(payload, sig)
        print("СТАТУС: ПОДЛИННЫЙ (подпись верна)")
        return 0
    except nacl.exceptions.BadSignatureError:
        print("СТАТУС: ПОДПИСЬ НЕДЕЙСТВИТЕЛЬНА", file=sys.stderr)
        return 2


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    p = argparse.ArgumentParser()
    p.add_argument("token")
    p.add_argument("--public", default="./keys/ed25519_public.key")
    args = p.parse_args(argv)
    return verify(args.token, args.public)


if __name__ == "__main__":
    raise SystemExit(main())
