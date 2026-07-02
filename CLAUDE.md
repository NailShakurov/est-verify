# CLAUDE.md — EST Certificate Generator (developer handoff)

Генератор именных PDF-сертификатов с персональным QR-кодом, подписанным Ed25519.
Читает таблицу выпускников (`.xlsx`) и пустой PDF-шаблон, на каждую строку
выпускает копию шаблона с ФИО, QR и лейблом домена проверки.

Design spec: `docs/superpowers/specs/2026-07-02-est-cert-generator-design.md`
Implementation plan: `docs/superpowers/plans/2026-07-02-est-cert-generator.md`

## Архитектура

Вся логика — в пакете `generator/estcert/`, изолированные модули, каждый
покрыт юнит-тестами (`generator/tests/`). `generator/generate.py` — тонкий CLI,
который связывает модули и реализует режимы (`--genkey`, `--check`,
`--preview`, `--compact`, батч). `generator/verify_token.py` — независимый
скрипт приёмочной проверки (не часть пакета `estcert`, использует его как
библиотеку).

Поток данных для одной строки таблицы:

```
xlsx row → validate → (cert_num, fio, course, date_iso)
                            │
                            ▼
                    payload (token.build_payload)
                            │
                            ▼
              signature = Ed25519_sign(private_key, payload)
                            │
                            ▼
            token = b64url(payload) + "." + b64url(signature)
                            │
                            ▼
                 URL = https://<domain>/#<token>
                            │
                            ▼
                    QR (segno, ECC=M) → PNG
                            │
                            ▼
     копия template.pdf + ФИО + QR + лейбл домена → output/<num>_<fio>.pdf
```

## Контракт токена (КРИТИЧНО — от него зависит совместимость с верификатором)

Дословно из дизайн-спеки (`docs/superpowers/specs/2026-07-02-est-cert-generator-design.md`),
соответствие с фактической реализацией в `generator/estcert/token.py` проверено:

```
поля      = [cert_num, fio, course, date_iso]      # позиционно, порядок жёсткий
payload   = "\x1f".join(поля).encode("utf-8")      # разделитель U+001F (unit separator)
signature = Ed25519_sign(private_key, payload)     # 64 байта, detached
token     = b64url_nopad(payload) + "." + b64url_nopad(signature)
URL       = https://est.com.kz/#<token>
```

Требования:
- `date_iso` — строго `YYYY-MM-DD`.
- `course` — полное `course_name` из конфига; при `--compact` — `course_code`.
- Данные лежат в фрагменте URL (`#...`), не в query — фрагмент не уходит на
  сервер при переходе по ссылке (152-ФЗ, ПДн).
- base64url БЕЗ паддинга (символ `=` обрезается).
- Разделитель `\x1f` не должен встречаться в данных: `validate.py` отклоняет
  строки таблицы с `\x1f` в номере/ФИО, `config.py` — конфиг с `\x1f` в
  `course_name`/`course_code`.

Реализация (`generator/estcert/token.py`):

```python
UNIT_SEP = "\x1f"

def b64url_nopad(data: bytes) -> str: ...      # base64.urlsafe_b64encode, rstrip("=")
def b64url_decode(s: str) -> bytes: ...        # добавляет паддинг обратно, urlsafe_b64decode
def build_payload(cert_num, fio, course, date_iso) -> bytes: ...  # UNIT_SEP.join(...).encode("utf-8")
def build_token(payload, signature) -> str: ...  # b64url_nopad(payload) + "." + b64url_nopad(signature)
def build_url(domain, token) -> str: ...         # f"https://{domain}/#{token}"
```

PyNaCl (Ed25519):

```python
sk  = nacl.signing.SigningKey(seed_bytes)   # seed 32 байта
sig = sk.sign(payload).signature            # 64 байта, detached
pub = sk.verify_key.encode()                # 32 байта → в верификатор
```

Ключи хранятся как base64-текст (`generator/estcert/keys.py`): приватный —
raw seed (32 байта) в base64, публичный — raw verify key (32 байта) в base64.
Совместимо с tweetnacl.js на стороне JS-верификатора.

## Карта файлов

```
est-cert/
  README.md                     # пользовательский гайд (установка, запуск, безопасность)
  CLAUDE.md                     # этот файл
  .gitignore                    # keys/, *.key, input/, output/, __pycache__/, .venv/, .pytest_cache/
  docs/superpowers/
    specs/2026-07-02-est-cert-generator-design.md   # исходная дизайн-спека
    plans/2026-07-02-est-cert-generator.md          # пошаговый план (11 задач)
  .superpowers/sdd/               # task-N-brief.md / task-N-report.md по каждой задаче
  generator/
    generate.py                  # CLI-вход: --genkey / --check / --preview [N] / --compact / батч
    verify_token.py              # standalone: decode token/URL + verify подпись публичным ключом
    config.yaml                  # домен, курс, пути, маппинг колонок, координаты placement
    requirements.txt             # PyMuPDF, segno, PyNaCl, openpyxl, PyYAML, pytest (запинены)
    pytest.ini                   # testpaths = tests
    assets/DejaVuSans.ttf         # бандл-шрифт (кириллица), закоммичен
    estcert/
      __init__.py
      config.py                  # load_config(): парсинг + валидация обязательных ключей и \x1f
      keys.py                    # genkey() / load_signing_key() / load_public_key() / sign()
      token.py                   # контракт токена (см. выше)
      table.py                   # read_rows(): openpyxl, маппинг колонок, normalize_date()
      validate.py                # validate_rows(): все ошибки списком, до генерации
      qr.py                      # make_qr() (segno, ECC=M), qr_version(), qr_png_bytes()
      render.py                  # render_certificate(): PyMuPDF, ФИО+QR+лейбл на копии шаблона
      pipeline.py                # build_token_for_row() / generate_one() — склейка одной строки
    tests/                       # test_token.py, test_keys.py, test_config.py, test_table.py,
                                  # test_validate.py, test_qr.py, test_render.py, test_pipeline.py,
                                  # test_cli.py, conftest.py (sys.path)
    keys/                        # GITIGNORED — ed25519_private.key (chmod 600) / ed25519_public.key
    input/                       # GITIGNORED — template.pdf + students.xlsx (ПДн заказчика)
    output/                      # GITIGNORED — готовые именные PDF (ПДн)
```

Примечание: дизайн-спека предусматривает отдельный каталог `verifier/`
(веб-страница проверки подписи по фрагменту URL) как отдельный бриф вне этого
плана — на момент завершения текущего 11-задачного плана каталог не создан и
в репозитории отсутствует.

## Режимы CLI (`generate.py`)

- `--genkey` — сгенерировать пару ключей Ed25519 в путях из `config.yaml`
  (`keys.private`, `keys.public`); отказывается перезаписать существующий
  приватный ключ (`FileExistsError`).
- `--check` — прочитать и провалидировать `table_path` без генерации PDF;
  печатает либо `OK: N строк готовы к генерации.`, либо список всех ошибок.
- `--preview [N]` — сгенерировать только первые `N` строк (по умолчанию 1),
  для выверки координат `placement` в конфиге.
- `--compact` — использовать `course_code` вместо `course_name` в payload/QR
  (эквивалентно `compact_course: true` в конфиге; флаг работает независимо от
  значения в конфиге).
- `--config <path>` — путь к конфигу (по умолчанию `config.yaml`).
- без флагов — полный батч по всем валидным строкам таблицы.

Все команды запускаются из каталога `generator/` — пути в `config.yaml`
относительны ему.

`verify_token.py "<token или URL>" --public ./keys/ed25519_public.key` —
независимая приёмочная проверка: декодирует 4 поля payload и печатает их,
проверяет Ed25519-подпись публичным ключом, печатает
`СТАТУС: ПОДЛИННЫЙ (подпись верна)` (exit 0) или
`СТАТУС: ПОДПИСЬ НЕДЕЙСТВИТЕЛЬНА` (exit 2, stderr).

## Ключи и ПДн — где лежат и правила безопасности

- `generator/keys/ed25519_private.key` — приватный ключ подписи, base64,
  создаётся с правами `chmod 600`. Гитигнорится. НИКОГДА не коммитится, не
  логируется, не копируется на сервер заказчика — существует только на машине,
  где выполняется генерация.
- `generator/keys/ed25519_public.key` — публичный ключ, base64. Гитигнорится
  наравне с приватным (в целях единообразия каталога `keys/`), но сам по себе
  безопасен для распространения — он нужен веб-верификатору и
  `verify_token.py`.
- `generator/input/template.pdf`, `generator/input/students.xlsx` — реальные
  данные заказчика (ПДн выпускников). Гитигнорится (`input/`).
- `generator/output/*.pdf` — сгенерированные именные сертификаты (тоже ПДн).
  Гитигнорится (`output/`).
- `.gitignore` (корень репозитория) закрывает: `keys/`, `*.key`, `input/`,
  `output/`, плюс служебные `__pycache__/`, `*.pyc`, `.pytest_cache/`,
  `.venv/`, `venv/`.
- При ручной заливке итоговых сертификатов на сервер заказчика (scp/rsync)
  нужно явно исключать `keys/`, `input/`, `output/` — заливаются только сами
  готовые PDF из `output/`, никогда рабочие каталоги генератора целиком.
- Данные QR лежат в фрагменте URL (`#...`), не в query-параметрах — не уходят
  на сервер при переходе по ссылке.

## Тесты

```bash
cd generator
source .venv/bin/activate
python -m pytest -q
```

41 тест на момент финальной задачи плана (token, keys, config, table,
validate, qr, render, pipeline, cli), все зелёные. `estcert/`-модули в этой
задаче не менялись — набор тестов и их результат не затронуты.

Юнит-тесты не требуют реальных файлов заказчика: fixtures в `tests/conftest.py`
и по месту в тестах создают синтетические PDF/xlsx через `fitz`/`openpyxl`.
