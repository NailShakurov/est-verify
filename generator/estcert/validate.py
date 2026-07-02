"""Валидация строк таблицы ДО генерации: собираем все ошибки списком."""
from collections import Counter

from estcert.table import normalize_date
from estcert.token import UNIT_SEP


def validate_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    clean: list[dict] = []

    counts = Counter(r["number"] for r in rows if r["number"])
    dup_numbers = {n for n, c in counts.items() if c > 1}

    for row in rows:
        r = row["row"]
        row_errors: list[str] = []

        if not row["number"]:
            row_errors.append(f"Строка {r}: пустой номер сертификата")
        elif row["number"] in dup_numbers:
            row_errors.append(f"Строка {r}: дубликат номера сертификата {row['number']!r}")

        if not row["fio"]:
            row_errors.append(f"Строка {r}: пустое ФИО")

        if UNIT_SEP in row["number"]:
            row_errors.append(f"Строка {r}: номер содержит запрещённый разделитель U+001F")
        if UNIT_SEP in row["fio"]:
            row_errors.append(f"Строка {r}: ФИО содержит запрещённый разделитель U+001F")

        date_iso = None
        try:
            date_iso = normalize_date(row["date_raw"])
        except ValueError:
            row_errors.append(f"Строка {r}: не распознана дата {row['date_raw']!r}")

        if row_errors:
            errors.extend(row_errors)
        else:
            clean.append({**row, "date_iso": date_iso})

    return clean, errors
