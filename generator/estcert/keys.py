"""Генерация/загрузка ключей Ed25519. Хранение — base64 (текст)."""
import base64
import os
from pathlib import Path

import nacl.signing


def genkey(private_path: str, public_path: str) -> None:
    if os.path.exists(private_path):
        raise FileExistsError(
            f"Приватный ключ уже существует: {private_path}. Удалите вручную, если действительно нужна новая пара."
        )
    Path(private_path).parent.mkdir(parents=True, exist_ok=True)
    Path(public_path).parent.mkdir(parents=True, exist_ok=True)

    sk = nacl.signing.SigningKey.generate()
    seed_b64 = base64.b64encode(bytes(sk)).decode("ascii")
    pub_b64 = base64.b64encode(sk.verify_key.encode()).decode("ascii")

    # приватник: создать с правами 600 сразу
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(seed_b64 + "\n")
    Path(public_path).write_text(pub_b64 + "\n")


def load_signing_key(private_path: str) -> nacl.signing.SigningKey:
    seed = base64.b64decode(Path(private_path).read_text().strip())
    return nacl.signing.SigningKey(seed)


def load_public_key(public_path: str) -> bytes:
    return base64.b64decode(Path(public_path).read_text().strip())


def sign(sk: nacl.signing.SigningKey, payload: bytes) -> bytes:
    return sk.sign(payload).signature
