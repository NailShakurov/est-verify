#!/usr/bin/env python3
"""EST — генератор именных сертификатов с подписанным QR. CLI-вход."""
import argparse
import sys

from estcert import config as cfgmod
from estcert import keys
from estcert import pipeline
from estcert import table as tablemod
from estcert import validate


def _load_and_validate(config):
    rows = tablemod.read_rows(config["table_path"], config["columns"])
    clean, errors = validate.validate_rows(rows)
    return clean, errors


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="EST генератор сертификатов")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--genkey", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--preview", nargs="?", type=int, const=1, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = cfgmod.load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Ошибка конфига: {e}", file=sys.stderr)
        return 1

    if args.genkey:
        try:
            keys.genkey(config["keys"]["private"], config["keys"]["public"])
        except FileExistsError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(f"Пара ключей создана:\n  приватный: {config['keys']['private']} (chmod 600)")
        print(f"  публичный: {config['keys']['public']}")
        print("ВНИМАНИЕ: приватный ключ НЕ копировать на сервер заказчика.")
        return 0

    compact = args.compact or bool(config.get("compact_course"))

    if args.check:
        try:
            clean, errors = _load_and_validate(config)
        except (FileNotFoundError, ValueError) as e:
            print(f"Ошибка таблицы: {e}", file=sys.stderr)
            return 1
        if errors:
            print(f"Найдено ошибок: {len(errors)}", file=sys.stderr)
            for e in errors:
                print("  - " + e, file=sys.stderr)
            return 1
        print(f"OK: {len(clean)} строк готовы к генерации.")
        return 0

    # preview / batch
    try:
        sk = keys.load_signing_key(config["keys"]["private"])
    except FileNotFoundError:
        print("Приватный ключ не найден. Сначала запустите --genkey.", file=sys.stderr)
        return 1

    try:
        clean, errors = _load_and_validate(config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Ошибка таблицы: {e}", file=sys.stderr)
        return 1
    if errors:
        print(f"Найдено ошибок: {len(errors)} — генерация отменена.", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1

    todo = clean[: args.preview] if args.preview is not None else clean
    print(f"Генерирую {len(todo)} сертификат(ов){' (compact)' if compact else ''}...")
    max_ver = 0
    for row in todo:
        res = pipeline.generate_one(sk, config, row, compact)
        max_ver = max(max_ver, res["qr_version"])
        print(f"  ✓ {res['path']} (QR v{res['qr_version']})")
    print(f"Готово. Максимальная версия QR: {max_ver}.")
    if max_ver > 10:
        print("ПРЕДУПРЕЖДЕНИЕ: версия QR > 10 — протестируйте печать+скан!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
