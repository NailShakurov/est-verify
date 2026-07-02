from estcert import validate


def _row(number="1", fio="Иван", date_raw="2026-07-02", r=2):
    return {"number": number, "fio": fio, "date_raw": date_raw, "row": r}


def test_all_valid():
    clean, errors = validate.validate_rows([_row(), _row(number="2", r=3)])
    assert errors == []
    assert clean[0]["date_iso"] == "2026-07-02"


def test_empty_fields_collected():
    clean, errors = validate.validate_rows([_row(number="", fio="")])
    assert len(errors) == 2  # пустой номер + пустое ФИО
    assert clean == []


def test_duplicate_numbers():
    clean, errors = validate.validate_rows([_row(number="1", r=2), _row(number="1", r=3)])
    assert any("дубл" in e.lower() for e in errors)


def test_bad_date_collected():
    clean, errors = validate.validate_rows([_row(date_raw="когда-то")])
    assert any("дат" in e.lower() for e in errors)
    assert clean == []


def test_separator_in_fio():
    clean, errors = validate.validate_rows([_row(fio="Ив\x1fан")])
    assert any("U+001F" in e for e in errors)
    assert clean == []


def test_errors_do_not_stop_at_first():
    rows = [_row(number="", r=2), _row(date_raw="плохо", r=3)]
    clean, errors = validate.validate_rows(rows)
    assert len(errors) >= 2
