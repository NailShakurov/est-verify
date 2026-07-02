"""Чтение таблицы выпускников (xlsx) и нормализация даты."""
import datetime as dt

import openpyxl

_DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]


def normalize_date(value) -> str:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str):
        s = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return dt.datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                continue
    raise ValueError(f"Не удалось распознать дату: {value!r}")


def _cell_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_rows(path: str, columns: dict) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        raise ValueError("Таблица пуста")

    header_map = {str(h).strip(): idx for idx, h in enumerate(header) if h is not None}
    idx = {}
    for field in ("number", "fio", "date"):
        title = columns[field]
        if title not in header_map:
            raise ValueError(f"В таблице нет колонки для поля '{field}': ожидался заголовок {title!r}")
        idx[field] = header_map[title]

    result = []
    for r, values in enumerate(rows_iter, start=2):
        number = _cell_str(values[idx["number"]]) if idx["number"] < len(values) else ""
        fio = _cell_str(values[idx["fio"]]) if idx["fio"] < len(values) else ""
        date_raw = values[idx["date"]] if idx["date"] < len(values) else None
        if not number and not fio and (date_raw is None or _cell_str(date_raw) == ""):
            continue
        result.append({"number": number, "fio": fio, "date_raw": date_raw, "row": r})
    return result
