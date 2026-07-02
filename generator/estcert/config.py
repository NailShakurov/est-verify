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
