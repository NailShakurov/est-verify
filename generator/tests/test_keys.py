import os
import stat
import pytest
import nacl.signing
from estcert import keys


def test_genkey_creates_base64_files_and_perms(tmp_path):
    priv = tmp_path / "k" / "priv.key"
    pub = tmp_path / "k" / "pub.key"
    keys.genkey(str(priv), str(pub))
    assert priv.exists() and pub.exists()
    mode = stat.S_IMODE(os.stat(priv).st_mode)
    assert mode == 0o600
    # base64 -> 32 байта seed / 32 байта pub
    import base64
    assert len(base64.b64decode(priv.read_text().strip())) == 32
    assert len(base64.b64decode(pub.read_text().strip())) == 32


def test_genkey_refuses_overwrite(tmp_path):
    priv = tmp_path / "priv.key"
    pub = tmp_path / "pub.key"
    keys.genkey(str(priv), str(pub))
    with pytest.raises(FileExistsError):
        keys.genkey(str(priv), str(pub))


def test_load_and_sign_roundtrip(tmp_path):
    priv = tmp_path / "priv.key"
    pub = tmp_path / "pub.key"
    keys.genkey(str(priv), str(pub))
    sk = keys.load_signing_key(str(priv))
    pubkey = keys.load_public_key(str(pub))
    payload = b"hello"
    sig = keys.sign(sk, payload)
    assert len(sig) == 64
    # проверяемо публичным ключом
    nacl.signing.VerifyKey(pubkey).verify(payload, sig)
