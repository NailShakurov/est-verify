# EST Certificate Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI-скрипт, который из xlsx-таблицы выпускников и PDF-шаблона выдаёт папку именных сертификатов с ФИО и персональным QR, внутри которого данные, подписанные Ed25519.

**Architecture:** Логика разбита на изолированные модули пакета `generator/estcert/` (token, keys, config, table, validate, qr, render), каждый с юнит-тестами. `generator/generate.py` — тонкий CLI-вход, связывающий модули и реализующий режимы. Приватный ключ никогда не покидает локальную машину; данные QR лежат во фрагменте URL.

**Tech Stack:** Python 3.11+, PyMuPDF (fitz), segno, PyNaCl, openpyxl, PyYAML, pytest.

## Global Constraints

- Контракт токена жёсткий: `поля = [cert_num, fio, course, date_iso]`, `payload = "\x1f".join(поля).encode("utf-8")`, `signature = Ed25519_sign(sk, payload)` (64 байта, detached), `token = b64url_nopad(payload) + "." + b64url_nopad(signature)`, `URL = https://<domain>/#<token>`.
- Разделитель полей — U+001F (`"\x1f"`). Любое поле или `course_name`/`course_code` с этим символом ОТКЛОНЯЕТСЯ.
- base64url БЕЗ паддинга (`=` убрать).
- `date_iso` строго `YYYY-MM-DD`.
- `course` в payload = `course_name`; при `--compact` = `course_code`.
- QR: библиотека segno, ECC = `M`. Сторона ≥ 85 pt (конфиг ставит 90). Warning при версии QR > 10.
- Ключи Ed25519 хранятся в base64 (текстовые файлы). Приватник пишется `chmod 600`.
- ФИО рендерится кириллическим TTF (`font_file` из конфига), центрируется по точке `x`, при переполнении `max_width` — авто-уменьшение шрифта до `fio_min_fontsize`.
- Печатать латинский лейбл домена `est.com.kz` под QR (анти-фишинг).
- `.gitignore` обязан включать `keys/`, `*.key`, `input/`, `output/`.
- Приватный ключ никогда не коммитится и не логируется.
- Все команды запускаются из каталога `generator/` (рабочая директория). Пути в конфиге относительны ему.

---

### Task 1: Каркас проекта, зависимости, шрифт, .gitignore

**Files:**
- Create: `.gitignore`
- Create: `generator/requirements.txt`
- Create: `generator/estcert/__init__.py`
- Create: `generator/tests/__init__.py`
- Create: `generator/tests/conftest.py`
- Create: `generator/assets/DejaVuSans.ttf` (скачивается)
- Create: `generator/pytest.ini`

**Interfaces:**
- Consumes: —
- Produces: рабочее окружение; пакет `estcert` импортируем; `pytest` запускается из `generator/`.

- [ ] **Step 1: Создать `.gitignore`**

```
keys/
*.key
input/
output/
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
```

- [ ] **Step 2: Создать `generator/requirements.txt`**

```
PyMuPDF==1.24.10
segno==1.6.1
PyNaCl==1.5.0
openpyxl==3.1.5
PyYAML==6.0.2
pytest==8.3.4
```

- [ ] **Step 3: Создать пустые `generator/estcert/__init__.py` и `generator/tests/__init__.py`**

Оба файла пустые.

- [ ] **Step 4: Создать `generator/pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 5: Создать `generator/tests/conftest.py`** (добавляет корень `generator/` в sys.path)

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 6: Установить зависимости и скачать шрифт**

Run:
```bash
cd generator
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
mkdir -p assets
curl -L -o assets/DejaVuSans.ttf https://github.com/dejavu-fonts/dejavu-fonts/raw/version_2_37/ttf/DejaVuSans.ttf
python -c "import fitz; f=fitz.Font(fontfile='assets/DejaVuSans.ttf'); print('font ok', f.name)"
```
Expected: `font ok` и имя шрифта (DejaVu Sans). Если curl не проходит — взять DejaVuSans.ttf из системных шрифтов (`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`) и скопировать в `assets/`.

- [ ] **Step 7: Проверить, что pytest стартует**

Run: `cd generator && python -m pytest -q`
Expected: `no tests ran` (0 тестов, без ошибок импорта).

- [ ] **Step 8: Commit**

```bash
git add .gitignore generator/requirements.txt generator/estcert generator/tests generator/pytest.ini generator/assets/DejaVuSans.ttf
git commit -m "chore: project scaffold, deps, bundled font, gitignore"
```

---

### Task 2: Модуль token — контракт токена

**Files:**
- Create: `generator/estcert/token.py`
- Test: `generator/tests/test_token.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `UNIT_SEP = "\x1f"`
  - `b64url_nopad(data: bytes) -> str`
  - `b64url_decode(s: str) -> bytes`
  - `build_payload(cert_num: str, fio: str, course: str, date_iso: str) -> bytes` — джойнит 4 поля через `UNIT_SEP`, кодирует utf-8; бросает `ValueError`, если любое поле содержит `UNIT_SEP`.
  - `build_token(payload: bytes, signature: bytes) -> str` — `b64url_nopad(payload) + "." + b64url_nopad(signature)`.
  - `build_url(domain: str, token: str) -> str` — `https://<domain>/#<token>`.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_token.py`**

```python
import base64
import pytest
from estcert import token as tk


def test_b64url_nopad_strips_padding():
    assert tk.b64url_nopad(b"\x00\x00") == "AAA"  # без "=="


def test_b64url_roundtrip():
    data = bytes(range(50))
    assert tk.b64url_decode(tk.b64url_nopad(data)) == data


def test_build_payload_positional_order_and_separator():
    p = tk.build_payload("№1", "Иванов Иван", "Курс", "2026-07-02")
    assert p == "№1\x1fИванов Иван\x1fКурс\x1f2026-07-02".encode("utf-8")


def test_build_payload_rejects_separator_in_field():
    with pytest.raises(ValueError):
        tk.build_payload("1", "Иван\x1fов", "Курс", "2026-07-02")


def test_build_token_shape():
    t = tk.build_token(b"payload", b"sig")
    left, right = t.split(".")
    assert tk.b64url_decode(left) == b"payload"
    assert tk.b64url_decode(right) == b"sig"


def test_build_url_uses_fragment():
    assert tk.build_url("est.com.kz", "TT") == "https://est.com.kz/#TT"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_token.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.token`).

- [ ] **Step 3: Реализовать `generator/estcert/token.py`**

```python
"""Контракт токена: payload по спеке, base64url без паддинга, сборка URL."""
import base64

UNIT_SEP = "\x1f"


def b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def build_payload(cert_num: str, fio: str, course: str, date_iso: str) -> bytes:
    fields = [cert_num, fio, course, date_iso]
    for f in fields:
        if UNIT_SEP in f:
            raise ValueError(f"Поле содержит запрещённый разделитель U+001F: {f!r}")
    return UNIT_SEP.join(fields).encode("utf-8")


def build_token(payload: bytes, signature: bytes) -> str:
    return b64url_nopad(payload) + "." + b64url_nopad(signature)


def build_url(domain: str, token: str) -> str:
    return f"https://{domain}/#{token}"
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_token.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/token.py generator/tests/test_token.py
git commit -m "feat: token contract (payload, b64url, url)"
```

---

### Task 3: Модуль keys — генерация и загрузка Ed25519

**Files:**
- Create: `generator/estcert/keys.py`
- Test: `generator/tests/test_keys.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `genkey(private_path: str, public_path: str) -> None` — создаёт директории, генерирует пару, пишет base64-строки (seed приватника 32 байта; пубключ 32 байта), приватник `chmod 600`. Если приватник уже существует — бросает `FileExistsError` (не перезаписывать втихую).
  - `load_signing_key(private_path: str) -> nacl.signing.SigningKey`
  - `load_public_key(public_path: str) -> bytes` — 32 байта.
  - `sign(sk: nacl.signing.SigningKey, payload: bytes) -> bytes` — 64 байта detached.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_keys.py`**

```python
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_keys.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.keys`).

- [ ] **Step 3: Реализовать `generator/estcert/keys.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_keys.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/keys.py generator/tests/test_keys.py
git commit -m "feat: Ed25519 key genkey/load/sign (base64, chmod 600)"
```

---

### Task 4: Модуль config — загрузка и валидация конфига

**Files:**
- Create: `generator/estcert/config.py`
- Create: `generator/config.yaml` (пример)
- Test: `generator/tests/test_config.py`

**Interfaces:**
- Consumes: `estcert.token.UNIT_SEP`
- Produces:
  - `load_config(path: str) -> dict` — читает YAML, валидирует обязательные ключи, бросает `ValueError` со списком проблем (join через `\n`), если: отсутствует обязательный ключ; `course_name` или `course_code` содержит `UNIT_SEP`. Возвращает dict как есть.
  - Обязательные ключи верхнего уровня: `domain`, `course_name`, `course_code`, `compact_course`, `template_pdf`, `table_path`, `output_dir`, `font_file`, `keys`, `columns`, `placement`.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_config.py`**

```python
import pytest
from estcert import config as cfg

VALID = """
domain: est.com.kz
course_name: "Курс"
course_code: "E"
compact_course: false
template_pdf: ./input/template.pdf
table_path: ./input/students.xlsx
output_dir: ./output
font_file: ./assets/DejaVuSans.ttf
keys:
  private: ./keys/priv.key
  public: ./keys/pub.key
columns:
  fio: "ФИО"
  date: "Дата"
  number: "Номер"
placement:
  fio: {x: 300, y: 250, fontsize: 18, fio_min_fontsize: 10, max_width: 260, color: "#000000"}
  qr: {x: 450, y: 600, size: 90}
  verify_label: {x: 450, y: 695, fontsize: 8, font: "helv"}
"""


def test_load_valid(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(VALID)
    c = cfg.load_config(str(p))
    assert c["domain"] == "est.com.kz"
    assert c["course_code"] == "E"


def test_missing_key_raises(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(VALID.replace("domain: est.com.kz", ""))
    with pytest.raises(ValueError) as e:
        cfg.load_config(str(p))
    assert "domain" in str(e.value)


def test_separator_in_course_name_raises(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(VALID.replace('course_name: "Курс"', 'course_name: "Ку\\x1fрс"'))
    # инъекция реального U+001F через python-yaml не тривиальна: подставим напрямую
    text = p.read_text().replace("Ку\\x1fрс", "Ку\x1fрс")
    p.write_text(text)
    with pytest.raises(ValueError):
        cfg.load_config(str(p))
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_config.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.config`).

- [ ] **Step 3: Реализовать `generator/estcert/config.py`**

```python
"""Загрузка и валидация config.yaml."""
import yaml

from estcert.token import UNIT_SEP

REQUIRED_TOP = [
    "domain", "course_name", "course_code", "compact_course",
    "template_pdf", "table_path", "output_dir", "font_file",
    "keys", "columns", "placement",
]


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    errors = []
    for key in REQUIRED_TOP:
        if key not in data or data[key] in (None, ""):
            errors.append(f"Отсутствует обязательный ключ конфига: {key}")

    for key in ("course_name", "course_code"):
        val = data.get(key)
        if isinstance(val, str) and UNIT_SEP in val:
            errors.append(f"{key} содержит запрещённый разделитель U+001F")

    if errors:
        raise ValueError("Ошибки конфига:\n" + "\n".join(errors))
    return data
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_config.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Создать пример `generator/config.yaml`**

```yaml
domain: est.com.kz
course_name: "Евразийская школа трекинга"   # входит в подписанный payload
course_code: "E"                             # используется при --compact
compact_course: false                        # true → в QR короткий код вместо названия

template_pdf: ./input/template.pdf
table_path: ./input/students.xlsx
output_dir: ./output
font_file: ./assets/DejaVuSans.ttf           # кириллический TTF для ФИО

keys:
  private: ./keys/ed25519_private.key   # ТОЛЬКО локально, на сервер заказчика не копировать
  public:  ./keys/ed25519_public.key

columns:            # маппинг наших полей на заголовки в таблице заказчика
  fio: "ФИО"
  date: "Дата выдачи"
  number: "Номер"

placement:          # координаты на шаблоне (точки PDF, начало — верхний левый угол)
  fio:  { x: 300, y: 250, fontsize: 18, fio_min_fontsize: 10, max_width: 260, color: "#000000" }
  qr:   { x: 450, y: 600, size: 90 }              # 90 pt ≈ 3.2 см (>= 3 см)
  verify_label: { x: 450, y: 695, fontsize: 8, font: "helv" }
```

- [ ] **Step 6: Commit**

```bash
git add generator/estcert/config.py generator/config.yaml generator/tests/test_config.py
git commit -m "feat: config loading + validation, example config.yaml"
```

---

### Task 5: Модуль table — чтение xlsx и нормализация даты

**Files:**
- Create: `generator/estcert/table.py`
- Test: `generator/tests/test_table.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `normalize_date(value) -> str` — принимает `datetime.datetime`/`datetime.date`/`str`; возвращает `YYYY-MM-DD`; бросает `ValueError` на нераспознанном. Поддержать строковые форматы: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD/MM/YYYY`.
  - `read_rows(path: str, columns: dict) -> list[dict]` — читает первый лист xlsx через openpyxl, по заголовкам первой строки находит колонки `columns["number"|"fio"|"date"]`; бросает `ValueError`, если какой-то заголовок не найден. Возвращает список dict-ов `{"number": str, "fio": str, "date_raw": <cell value>, "row": <номер строки 1-based>}`. Пустые строки (все три ячейки пусты) пропускаются.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_table.py`**

```python
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_table.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.table`).

- [ ] **Step 3: Реализовать `generator/estcert/table.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_table.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/table.py generator/tests/test_table.py
git commit -m "feat: xlsx reading with column mapping + date normalization"
```

---

### Task 6: Модуль validate — валидация всех строк списком

**Files:**
- Create: `generator/estcert/validate.py`
- Test: `generator/tests/test_validate.py`

**Interfaces:**
- Consumes: `estcert.table.normalize_date`, `estcert.token.UNIT_SEP`
- Produces:
  - `validate_rows(rows: list[dict]) -> tuple[list[dict], list[str]]` — возвращает `(clean_rows, errors)`. `clean_rows` — строки с добавленным полем `date_iso` (нормализованная дата). `errors` — список человекочитаемых сообщений. Проверки: пустой `number`; пустой `fio`; дубли `number` (сообщение на каждый повтор); нераспознанная дата; наличие `UNIT_SEP` в `number` или `fio`. Строка попадает в `clean_rows` только если по ней нет ошибок.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_validate.py`**

```python
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_validate.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.validate`).

- [ ] **Step 3: Реализовать `generator/estcert/validate.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_validate.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/validate.py generator/tests/test_validate.py
git commit -m "feat: row validation collecting all errors as a list"
```

---

### Task 7: Модуль qr — генерация QR (segno, ECC=M) + проверка версии

**Files:**
- Create: `generator/estcert/qr.py`
- Test: `generator/tests/test_qr.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `make_qr(data: str) -> segno.QRCode` — `segno.make(data, error="m")`.
  - `qr_version(qrcode) -> int` — числовая версия (`qrcode.version`, для микро-QR вернуть как есть; ожидаем обычный QR).
  - `qr_png_bytes(qrcode, target_pt: float, dpi: int = 300) -> bytes` — рендер в PNG (io.BytesIO) с масштабом, дающим сторону ≈ `target_pt` при печати; возвращает bytes. Расчёт scale: `border=1`, `scale` подбирается так, чтобы картинка была достаточного разрешения (используем `scale` из расчёта `dpi`); фактический размер на PDF задаётся при вставке, PNG нужен резким.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_qr.py`**

```python
from estcert import qr


def test_make_qr_ecc_m():
    q = qr.make_qr("hello")
    assert q.error.lower() == "m"


def test_version_is_int():
    q = qr.make_qr("hello")
    assert isinstance(qr.qr_version(q), int)


def test_long_payload_higher_version():
    short = qr.qr_version(qr.make_qr("x"))
    long = qr.qr_version(qr.make_qr("x" * 230))
    assert long > short


def test_png_bytes_are_png():
    q = qr.make_qr("hello")
    data = qr.qr_png_bytes(q, target_pt=90)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_qr.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.qr`).

- [ ] **Step 3: Реализовать `generator/estcert/qr.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_qr.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/qr.py generator/tests/test_qr.py
git commit -m "feat: QR generation (segno ECC=M) + version + png render"
```

---

### Task 8: Модуль render — нанесение ФИО, QR и лейбла на PDF

**Files:**
- Create: `generator/estcert/render.py`
- Test: `generator/tests/test_render.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `hex_to_rgb(hex_color: str) -> tuple[float, float, float]` — `"#000000"` → `(0.0, 0.0, 0.0)`.
  - `fit_fontsize(font, text, fontsize, min_fontsize, max_width) -> float` — уменьшает `fontsize` шагами по 0.5 вниз до `min_fontsize`, пока `font.text_length(text, size) > max_width`; возвращает подобранный размер (не меньше `min_fontsize`).
  - `sanitize_filename(fio) -> str` — пробелы→`_`, удаляет `/ \ : * ? " < > |`, схлопывает повторные `_`, кириллицу сохраняет.
  - `render_certificate(template_pdf, output_path, fio, qr_png, placement, font_file, domain_label) -> None` — копирует шаблон, впечатывает ФИО (центр по `placement["fio"]["x"]`, авто-fit по `max_width`), вставляет QR (квадрат `size` pt, левый-верх в `placement["qr"]["x"|"y"]`), впечатывает `domain_label` латинским `helv` по `verify_label`. Сохраняет PDF.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_render.py`**

```python
import fitz
import pytest
from estcert import render, qr

FONT = "assets/DejaVuSans.ttf"


def test_hex_to_rgb():
    assert render.hex_to_rgb("#000000") == (0.0, 0.0, 0.0)
    assert render.hex_to_rgb("#ffffff") == (1.0, 1.0, 1.0)


def test_sanitize_filename():
    assert render.sanitize_filename("Иванов Иван") == "Иванов_Иван"
    assert "/" not in render.sanitize_filename("a/b:c")


def test_fit_fontsize_shrinks():
    font = fitz.Font(fontfile=FONT)
    size = render.fit_fontsize(font, "Очень длинное имя фамилия отчество", 18, 6, 50)
    assert size < 18
    assert size >= 6


def test_render_creates_pdf(tmp_path):
    # шаблон: пустая A4-страница
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    template = tmp_path / "template.pdf"
    doc.save(str(template))
    doc.close()

    q = qr.make_qr("https://est.com.kz/#TT")
    png = qr.qr_png_bytes(q, target_pt=90)
    placement = {
        "fio": {"x": 300, "y": 250, "fontsize": 18, "fio_min_fontsize": 10, "max_width": 260, "color": "#000000"},
        "qr": {"x": 450, "y": 600, "size": 90},
        "verify_label": {"x": 450, "y": 695, "fontsize": 8, "font": "helv"},
    }
    out = tmp_path / "out.pdf"
    render.render_certificate(str(template), str(out), "Иванов Иван", png,
                              placement, FONT, "est.com.kz")
    assert out.exists()
    text = fitz.open(str(out))[0].get_text()
    assert "Иванов Иван" in text
    assert "est.com.kz" in text
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_render.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.render`).

- [ ] **Step 3: Реализовать `generator/estcert/render.py`**

```python
"""Нанесение ФИО, QR и лейбла домена на копию шаблона PDF (PyMuPDF)."""
import io
import re

import fitz

_FIO_FONTNAME = "estfio"


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def sanitize_filename(fio: str) -> str:
    name = fio.strip().replace(" ", "_")
    name = re.sub(r'[/\\:*?"<>|]', "", name)
    name = re.sub(r"_+", "_", name)
    return name


def fit_fontsize(font, text, fontsize, min_fontsize, max_width) -> float:
    size = float(fontsize)
    while size > min_fontsize and font.text_length(text, size) > max_width:
        size -= 0.5
    return max(size, float(min_fontsize))


def render_certificate(template_pdf, output_path, fio, qr_png, placement,
                       font_file, domain_label) -> None:
    doc = fitz.open(template_pdf)
    page = doc[0]

    # --- ФИО (кириллический TTF, центр по x, авто-fit) ---
    fio_cfg = placement["fio"]
    font = fitz.Font(fontfile=font_file)
    page.insert_font(fontname=_FIO_FONTNAME, fontfile=font_file)
    size = fit_fontsize(font, fio, fio_cfg["fontsize"],
                        fio_cfg.get("fio_min_fontsize", fio_cfg["fontsize"]),
                        fio_cfg.get("max_width", float("inf")))
    tw = font.text_length(fio, size)
    x = fio_cfg["x"] - tw / 2.0
    page.insert_text((x, fio_cfg["y"]), fio, fontname=_FIO_FONTNAME,
                     fontsize=size, color=hex_to_rgb(fio_cfg.get("color", "#000000")))

    # --- QR ---
    qr_cfg = placement["qr"]
    s = qr_cfg["size"]
    rect = fitz.Rect(qr_cfg["x"], qr_cfg["y"], qr_cfg["x"] + s, qr_cfg["y"] + s)
    page.insert_image(rect, stream=io.BytesIO(qr_png))

    # --- лейбл домена (латиница, helv) ---
    lbl = placement["verify_label"]
    page.insert_text((lbl["x"], lbl["y"]), domain_label,
                     fontname=lbl.get("font", "helv"), fontsize=lbl["fontsize"],
                     color=(0, 0, 0))

    doc.save(output_path)
    doc.close()
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_render.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/render.py generator/tests/test_render.py
git commit -m "feat: PDF render (centered Cyrillic FIO, QR, domain label)"
```

---

### Task 9: Пайплайн генерации — сборка одного сертификата end-to-end

**Files:**
- Create: `generator/estcert/pipeline.py`
- Test: `generator/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `estcert.token`, `estcert.keys`, `estcert.qr`, `estcert.render`
- Produces:
  - `course_for(config, compact: bool) -> str` — возвращает `config["course_code"]` если `compact`, иначе `config["course_name"]`.
  - `build_token_for_row(sk, config, row, compact: bool) -> tuple[str, str, int]` — собирает payload (`number, fio, course, date_iso`), подписывает, возвращает `(token, url, qr_version)`.
  - `generate_one(sk, config, row, compact: bool) -> dict` — полный цикл: token→QR→render в `output/<number>_<fio>.pdf`; возвращает `{"path": str, "qr_version": int, "url": str}`. Печатает warning (через `warnings.warn`) при `qr_version > 10`.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_pipeline.py`**

```python
import base64
import fitz
import nacl.signing
import pytest
from estcert import pipeline, keys, token as tk


@pytest.fixture
def setup(tmp_path):
    # шаблон
    doc = fitz.open(); doc.new_page(width=595, height=842)
    template = tmp_path / "template.pdf"; doc.save(str(template)); doc.close()
    # ключи
    priv = tmp_path / "priv.key"; pub = tmp_path / "pub.key"
    keys.genkey(str(priv), str(pub))
    sk = keys.load_signing_key(str(priv))
    pubkey = keys.load_public_key(str(pub))
    config = {
        "domain": "est.com.kz",
        "course_name": "Евразийская школа трекинга",
        "course_code": "E",
        "template_pdf": str(template),
        "output_dir": str(tmp_path / "out"),
        "font_file": "assets/DejaVuSans.ttf",
        "placement": {
            "fio": {"x": 300, "y": 250, "fontsize": 18, "fio_min_fontsize": 10, "max_width": 260, "color": "#000000"},
            "qr": {"x": 450, "y": 600, "size": 90},
            "verify_label": {"x": 450, "y": 695, "fontsize": 8, "font": "helv"},
        },
    }
    row = {"number": "001", "fio": "Иванов Иван", "date_iso": "2026-07-02", "row": 2}
    return sk, pubkey, config, row


def test_course_for():
    cfg = {"course_name": "Полное", "course_code": "E"}
    assert pipeline.course_for(cfg, False) == "Полное"
    assert pipeline.course_for(cfg, True) == "E"


def test_token_verifies_with_pubkey(setup):
    sk, pubkey, config, row = setup
    token, url, ver = pipeline.build_token_for_row(sk, config, row, compact=False)
    payload_b64, sig_b64 = token.split(".")
    payload = tk.b64url_decode(payload_b64)
    sig = tk.b64url_decode(sig_b64)
    nacl.signing.VerifyKey(pubkey).verify(payload, sig)  # не бросает
    assert payload.decode("utf-8").split("\x1f") == [
        "001", "Иванов Иван", "Евразийская школа трекинга", "2026-07-02"]


def test_generate_one_writes_pdf(setup):
    sk, pubkey, config, row = setup
    res = pipeline.generate_one(sk, config, row, compact=False)
    assert res["path"].endswith("001_Иванов_Иван.pdf")
    import os
    assert os.path.exists(res["path"])
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_pipeline.py -q`
Expected: FAIL (`ModuleNotFoundError: estcert.pipeline`).

- [ ] **Step 3: Реализовать `generator/estcert/pipeline.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_pipeline.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add generator/estcert/pipeline.py generator/tests/test_pipeline.py
git commit -m "feat: single-certificate pipeline (token -> QR -> PDF)"
```

---

### Task 10: CLI `generate.py` — режимы genkey/check/preview/compact/batch

**Files:**
- Create: `generator/generate.py`
- Test: `generator/tests/test_cli.py`

**Interfaces:**
- Consumes: все модули `estcert.*`
- Produces:
  - `main(argv: list[str]) -> int` — парсит аргументы (`--config` по умолчанию `config.yaml`, `--genkey`, `--preview [N]` (nargs="?", const=1), `--check`, `--compact`), возвращает код возврата (0 успех, 1 ошибки валидации/конфига). Режимы:
    - `--genkey`: `keys.genkey(...)`, печать путей, `return 0`.
    - `--check`: загрузить конфиг, прочитать таблицу, `validate_rows`; если есть ошибки — вывести списком и `return 1`; иначе «OK, N строк» и `return 0`. Ключи не требуются.
    - `--preview N` / batch: загрузить конфиг, ключи, таблицу, валидация; при ошибках — список и `return 1`; иначе сгенерировать (N строк для preview, все — для batch), печать прогресса и итога, `return 0`.
  - `compact` берётся из `args.compact or config["compact_course"]`.

- [ ] **Step 1: Написать падающий тест `generator/tests/test_cli.py`**

```python
import os
import openpyxl
import fitz
from estcert import keys
import generate


def _write_config(tmp_path, template, table, keysdir, outdir):
    cfg = f"""
domain: est.com.kz
course_name: "Евразийская школа трекинга"
course_code: "E"
compact_course: false
template_pdf: {template}
table_path: {table}
output_dir: {outdir}
font_file: assets/DejaVuSans.ttf
keys:
  private: {keysdir}/priv.key
  public: {keysdir}/pub.key
columns:
  fio: "ФИО"
  date: "Дата выдачи"
  number: "Номер"
placement:
  fio: {{x: 300, y: 250, fontsize: 18, fio_min_fontsize: 10, max_width: 260, color: "#000000"}}
  qr: {{x: 450, y: 600, size: 90}}
  verify_label: {{x: 450, y: 695, fontsize: 8, font: "helv"}}
"""
    p = tmp_path / "config.yaml"
    p.write_text(cfg)
    return str(p)


def _make_table(path, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Номер", "ФИО", "Дата выдачи"])
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_genkey_mode(tmp_path):
    kd = tmp_path / "keys"
    cfg = _write_config(tmp_path, "t.pdf", "s.xlsx", str(kd), str(tmp_path / "out"))
    rc = generate.main(["--config", cfg, "--genkey"])
    assert rc == 0
    assert (kd / "priv.key").exists()


def test_check_reports_errors(tmp_path):
    table = str(tmp_path / "s.xlsx")
    _make_table(table, [["", "Иван", "2026-07-02"]])  # пустой номер
    cfg = _write_config(tmp_path, "t.pdf", table, str(tmp_path / "k"), str(tmp_path / "out"))
    rc = generate.main(["--config", cfg, "--check"])
    assert rc == 1


def test_batch_generates(tmp_path):
    # шаблон
    doc = fitz.open(); doc.new_page(width=595, height=842)
    template = str(tmp_path / "t.pdf"); doc.save(template); doc.close()
    table = str(tmp_path / "s.xlsx")
    _make_table(table, [["001", "Иванов Иван", "2026-07-02"],
                        ["002", "Пётр Петров", "2026-07-02"]])
    kd = tmp_path / "k"; outdir = tmp_path / "out"
    cfg = _write_config(tmp_path, template, table, str(kd), str(outdir))
    assert generate.main(["--config", cfg, "--genkey"]) == 0
    rc = generate.main(["--config", cfg])
    assert rc == 0
    assert os.path.exists(str(outdir / "001_Иванов_Иван.pdf"))
    assert os.path.exists(str(outdir / "002_Пётр_Петров.pdf"))


def test_preview_limits_count(tmp_path):
    doc = fitz.open(); doc.new_page(width=595, height=842)
    template = str(tmp_path / "t.pdf"); doc.save(template); doc.close()
    table = str(tmp_path / "s.xlsx")
    _make_table(table, [["001", "A B", "2026-07-02"], ["002", "C D", "2026-07-02"]])
    kd = tmp_path / "k"; outdir = tmp_path / "out"
    cfg = _write_config(tmp_path, template, table, str(kd), str(outdir))
    generate.main(["--config", cfg, "--genkey"])
    rc = generate.main(["--config", cfg, "--preview", "1"])
    assert rc == 0
    assert len(list(outdir.glob("*.pdf"))) == 1
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd generator && python -m pytest tests/test_cli.py -q`
Expected: FAIL (`ModuleNotFoundError: generate`).

- [ ] **Step 3: Реализовать `generator/generate.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd generator && python -m pytest tests/test_cli.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Прогнать весь тест-сьют**

Run: `cd generator && python -m pytest -q`
Expected: PASS (все тесты зелёные).

- [ ] **Step 6: Commit**

```bash
git add generator/generate.py generator/tests/test_cli.py
git commit -m "feat: CLI with genkey/check/preview/compact/batch modes"
```

---

### Task 11: verify_token.py + README + CLAUDE.md

**Files:**
- Create: `generator/verify_token.py`
- Create: `README.md`
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: `estcert.token`, `estcert.keys`
- Produces: standalone `verify_token.py` — на вход token (или URL) и путь к пубключу, декодирует payload, проверяет подпись, печатает 4 поля и статус.

- [ ] **Step 1: Реализовать `generator/verify_token.py`**

```python
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
```

- [ ] **Step 2: Ручная проверка end-to-end**

Run:
```bash
cd generator
python generate.py --genkey        # если ключей ещё нет
# положить input/template.pdf и input/students.xlsx (2-3 строки)
python generate.py --check
python generate.py --preview 1
# взять URL из вывода preview (или из QR) и проверить:
python verify_token.py "<URL из preview>" --public ./keys/ed25519_public.key
```
Expected: `СТАТУС: ПОДЛИННЫЙ`.

- [ ] **Step 3: Создать `README.md`**

Содержимое: установка (venv + requirements), скачивание шрифта (или откуда взялся), генерация ключей (`--genkey`, предупреждение про приватник), подготовка `input/` (шаблон + xlsx, маппинг колонок в конфиге), выверка координат через `--preview`, запуск батча, `--compact`, приёмочный тест через `verify_token.py`, раздел безопасности (ключи/ПДн, ручная заливка scp с исключениями).

- [ ] **Step 4: Создать `CLAUDE.md`**

Содержимое (хэндофф): архитектура (пакет `estcert/` + `generate.py`), контракт токена (скопировать блок), карта файлов (что где), режимы CLI, где лежат ключи/ПДн и правила безопасности, как гонять тесты (`python -m pytest`).

- [ ] **Step 5: Commit**

```bash
git add generator/verify_token.py README.md CLAUDE.md
git commit -m "feat: verify_token acceptance script + README + CLAUDE.md"
```

---

## Self-Review

**Spec coverage:**
- Контракт токена → Task 2 ✓; подпись Ed25519 → Task 3 ✓; курс из конфига + payload → Task 9 ✓
- Чтение/валидация таблицы, ошибки списком → Tasks 5, 6 ✓
- Компактный режим (course_code) → Tasks 4, 9, 10 ✓
- QR segno ECC=M, версия ≤10 warning → Task 7, 9 ✓
- ФИО+QR+лейбл на PDF, кириллица, центрирование, ≥3см → Task 8 ✓
- Режимы genkey/preview/check/compact/batch → Task 10 ✓
- README + CLAUDE.md → Task 11 ✓
- .gitignore (keys/, *.key, input/, output/) → Task 1 ✓
- Приёмочный тест (декод+verify) → Task 11 ✓
- Ключи base64, chmod 600 → Task 3 ✓
- Бандл-шрифт → Task 1 ✓

**Placeholder scan:** README/CLAUDE.md в Task 11 описаны разделами, а не готовым текстом — это документация под свободное наполнение по перечисленным пунктам, допустимо; весь код приведён полностью.

**Type consistency:** `sanitize_filename`, `render_certificate`, `qr_png_bytes(target_pt=...)`, `build_payload`, `build_token`, `load_public_key`, `keys.sign` — имена согласованы между Tasks 2/3/7/8/9/10/11 ✓. `placement` dict-структура одинакова во всех задачах ✓.
