import datetime as dt
import openpyxl
import pytest
from estcert import table


def _make_xlsx(tmp_path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    p = tmp_path / "students.xlsx"
    wb.save(str(p))
    return str(p)


COLS = {"number": "Номер", "fio": "ФИО", "date": "Дата выдачи"}


def test_normalize_date_from_datetime():
    assert table.normalize_date(dt.datetime(2026, 7, 2)) == "2026-07-02"


def test_normalize_date_from_iso_str():
    assert table.normalize_date("2026-07-02") == "2026-07-02"


def test_normalize_date_from_dotted_str():
    assert table.normalize_date("02.07.2026") == "2026-07-02"


def test_normalize_date_bad_raises():
    with pytest.raises(ValueError):
        table.normalize_date("завтра")


def test_read_rows_maps_columns(tmp_path):
    p = _make_xlsx(tmp_path, ["Номер", "ФИО", "Дата выдачи"],
                   [["001", "Иванов Иван", dt.datetime(2026, 7, 2)]])
    rows = table.read_rows(p, COLS)
    assert rows[0]["number"] == "001"
    assert rows[0]["fio"] == "Иванов Иван"
    assert rows[0]["row"] == 2


def test_read_rows_missing_header_raises(tmp_path):
    p = _make_xlsx(tmp_path, ["Num", "ФИО", "Дата выдачи"], [])
    with pytest.raises(ValueError):
        table.read_rows(p, COLS)


def test_read_rows_skips_empty(tmp_path):
    p = _make_xlsx(tmp_path, ["Номер", "ФИО", "Дата выдачи"],
                   [[None, None, None], ["002", "Пётр", "01.01.2026"]])
    rows = table.read_rows(p, COLS)
    assert len(rows) == 1
    assert rows[0]["number"] == "002"
