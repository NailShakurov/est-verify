# EST — генератор именных сертификатов с подписанным QR

CLI-скрипт: таблица выпускников (`.xlsx`) + PDF-шаблон → папка именных PDF-сертификатов.
На каждый сертификат наносятся ФИО и персональный QR-код с данными, подписанными
Ed25519. Подлинность проверяется по QR (веб-верификатор) или локально через
`verify_token.py`.

## Установка

```bash
cd generator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Быстрый старт

```bash
python generate.py --genkey     # один раз: пара ключей Ed25519
# положить input/template.pdf и input/students.xlsx
python generate.py --check      # валидация таблицы, без генерации
python generate.py --preview    # 1 сертификат — сверить координаты в config.yaml
python generate.py              # полный батч
python generate.py --compact    # короткий код курса в QR вместо полного названия
```

Маппинг колонок таблицы, координаты ФИО/QR/лейбла и параметры курса задаются в
`config.yaml`.

## Приёмочная проверка

```bash
python verify_token.py "<URL или токен>" --public ./keys/ed25519_public.key
```

## Безопасность

Приватный ключ (`keys/ed25519_private.key`) никогда не коммитится и не покидает
локальную машину. Персональные данные (`input/`, `output/`) тоже не коммитятся —
см. `.gitignore`.

## Тесты

```bash
python -m pytest -q
```

## Верификатор (`index.html`)

Статическая страница проверки подлинности сертификата — QR ведёт на
`https://est.com.kz/#<token>`, страница разбирает токен из фрагмента URL и
проверяет Ed25519-подпись прямо в браузере (tweetnacl.js, без бэкенда).

Перед деплоем нужно один раз вставить публичный ключ: открыть
`index.html`, найти константу

```javascript
const PUBLIC_KEY_B64 = "REPLACE_WITH_ed25519_public.key_CONTENTS";
```

и заменить значение на содержимое файла `generator/keys/ed25519_public.key`
(одна строка base64, без переноса строки в конце).
