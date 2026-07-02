# EST — генератор именных сертификатов с подписанным QR (design)

Дата: 2026-07-02

## Цель

CLI-скрипт: на вход таблица выпускников (xlsx) + пустой PDF-шаблон, на выходе папка
готовых именных PDF. На каждый сертификат наносится ФИО и персональный QR. Внутри QR —
данные сертификата, закрытые подписью Ed25519. Проверка подлинности — статическая
страница `verifier/` (отдельный бриф), читает данные из фрагмента URL и проверяет
подпись публичным ключом.

Корень доверия: цифровая подпись + печатный домен проверки `est.com.kz` на бумаге.

## Стек (фиксированный)

- Python 3.11+
- PyMuPDF (`fitz`) — текст и QR на PDF
- segno — генерация QR (ECC=M)
- PyNaCl — подпись Ed25519 (парно совместима с tweetnacl.js в верификаторе)
- openpyxl — чтение xlsx (легче pandas)
- Зависимости запинены в `requirements.txt`

## Контракт токена (КРИТИЧНО — верификатор пишется под него)

```
поля      = [cert_num, fio, course, date_iso]      # позиционно, порядок жёсткий
payload   = "\x1f".join(поля).encode("utf-8")      # разделитель U+001F (unit separator)
signature = Ed25519_sign(private_key, payload)     # 64 байта, detached
token     = b64url_nopad(payload) + "." + b64url_nopad(signature)
URL       = https://est.com.kz/#<token>
```

Требования:
- `date_iso` — `YYYY-MM-DD`.
- `course` — полное `course_name` из конфига; при `--compact` — `course_code`.
- Данные в фрагменте URL (`#...`), не в query (не уходят на сервер; 152-ФЗ).
- base64url без паддинга (`=` убрать).
- Разделитель `\x1f` не встречается в данных. Скрипт ОТКЛОНЯЕТ строку (и значения
  `course_name` / `course_code`), если любое поле содержит этот символ.

PyNaCl:
```python
sk  = nacl.signing.SigningKey(seed_bytes)   # seed 32 байта
sig = sk.sign(payload).signature            # 64 байта
pub = sk.verify_key.encode()                # 32 байта → в верификатор
```

## Структура репо

```
est-cert/
  generator/
    generate.py
    verify_token.py        # мини-скрипт приёмочного теста (декод + verify)
    config.yaml
    requirements.txt
    assets/DejaVuSans.ttf   # бандл-шрифт для кириллицы (закоммичен)
    keys/                   # gitignored — ed25519_private.key / _public.key (base64)
    input/                  # gitignored (ПДн)
    output/                 # gitignored (ПДн)
  verifier/                 # пусто пока (отдельный бриф)
  README.md
  CLAUDE.md
  .gitignore
```

## Модули внутри `generate.py`

Изолированные функции, каждая тестируется отдельно.

- **config** — загрузка/валидация `config.yaml`; проверка, что `course_name` и
  `course_code` не содержат `\x1f`.
- **keys** — `genkey()` (пара Ed25519, приватник `chmod 600`, оба файла в base64);
  `load_signing_key()`, `load_public_key()`.
- **token** — payload по контракту, detached-подпись, `b64url_nopad`, token + URL.
- **table** — чтение xlsx (openpyxl), маппинг колонок из конфига, нормализация даты в
  `YYYY-MM-DD` (принимает datetime-ячейку и строку).
- **validate** — все строки ДО генерации: пустые поля, дубли номеров, кривые даты,
  запрещённый `\x1f`. Ошибки собираются списком, не падаем на первой.
- **qr** — segno, ECC=M; проверка версии, warning при >10; рендер PNG для вставки.
- **render** — копия шаблона (PyMuPDF); ФИО с центрированием по точке + авто-уменьшение
  шрифта при переполнении; QR (сторона из конфига, ≥85pt); лейбл `est.com.kz` под QR.
  Кириллица через бандл-TTF (`insert_font(fontfile=...)`).
- **cli** — режимы: `--genkey`, `--preview [N]`, `--check`, `--compact`, батч.

## Решения поверх брифа

1. **Кириллица:** конфиг получает `font_file: ./assets/DejaVuSans.ttf`. Поле `font:
   "helv"` остаётся только для латинского лейбла `est.com.kz`.
2. **Ключи в base64** (текстовые файлы). Пубключ base64 → прямо в JS-верификатор.
3. **ФИО центрируется** по `x` (точка = центр строки), при переполнении ширины —
   авто-уменьшение fontsize вниз до минимума (`fio_min_fontsize`).
4. **`course_code` в конфиге** (напр. `E`) для `--compact`; словарь код→название
   держит верификатор.
5. **Имя файла:** `output/<cert_num>_<fio>.pdf`, ФИО санитизируется (пробелы→`_`,
   убираются `/ \ : * ? " < > |`), кириллица сохраняется.
6. **verify_token.py** — приёмочный тест: декод token, проверка подписи пубключом.

## Конфиг (пример)

```yaml
domain: est.com.kz
course_name: "Евразийская школа трекинга"   # входит в подписанный payload
course_code: "E"                             # используется при --compact
compact_course: false

template_pdf: ./input/template.pdf
table_path: ./input/students.xlsx
output_dir: ./output
font_file: ./assets/DejaVuSans.ttf           # кириллический TTF для ФИО

keys:
  private: ./keys/ed25519_private.key
  public:  ./keys/ed25519_public.key

columns:
  fio: "ФИО"
  date: "Дата выдачи"
  number: "Номер"

placement:
  fio:  { x: 300, y: 250, fontsize: 18, fio_min_fontsize: 10, color: "#000000" }
  qr:   { x: 450, y: 600, size: 90 }              # 90 pt ≈ 3.2 см (>= 3 см)
  verify_label: { x: 450, y: 695, fontsize: 8, font: "helv" }
```

## Режимы CLI

- `--genkey` — сгенерить пару Ed25519 (приватник chmod 600).
- `--preview [N]` — только первые N (по умолчанию 1) — выверить координаты.
- `--check` — валидация таблицы/ключей без генерации.
- `--compact` — короткий код курса вместо полного названия.
- без флагов — полный батч.

## Функциональные требования

1. Маппинг колонок из конфига (заголовки у заказчика любые).
2. Валидация всех строк ДО генерации, ошибки списком.
3. На строку: курс из конфига → payload → подпись → token → QR (ECC=M) → копия
   шаблона → ФИО + QR + лейбл → `output/<cert_num>_<fio>.pdf`.
4. QR ≥ 3 см (≈85pt; в конфиге 90pt с запасом).
5. Печатать домен `est.com.kz` рядом с QR (анти-фишинг).
6. Warning при версии QR > 10.

## Безопасность

- Приватный ключ — только локально; не коммитится, не логируется, не копируется на
  сервер заказчика.
- `.gitignore`: `keys/`, `*.key`, `input/`, `output/`.
- При ручной заливке (scp/rsync) исключать `keys/`, `input/`, `output/` явно.
- Публичный ключ безопасен → в JS верификатора (base64).

## Приёмочный тест

Сгенерить 2-3 сертификата, декодировать token через `verify_token.py`, проверить
подпись пубключом, распечатать и отсканировать телефоном — убедиться, что QR ~v10
читается.
