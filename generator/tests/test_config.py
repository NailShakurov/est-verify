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
font_path: /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
keys:
  private: ./keys/priv.key
  public: ./keys/pub.key
columns:
  fio: "ФИО"
  date: "Дата"
  number: "Номер"
placement:
  fio: {rect: [59, 430, 767, 487], fontsize: 32, color: [0.1, 0.1, 0.5]}
  date: {x: 120, y: 828, fontsize: 15, color: [0, 0, 0]}
  cert_num: {x: 400, y: 960, fontsize: 13, color: [0.3, 0.3, 0.3]}
  qr: {x: 570, y: 800, size: 180}
  verify_label: {x: 570, y: 994, fontsize: 15, color: [0.2, 0.2, 0.6]}
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
    # Use YAML's \u escape syntax so YAML parses it and validation catches UNIT_SEP
    p.write_text(VALID.replace('course_name: "Курс"', 'course_name: "Ку\\u001fрс"'))
    with pytest.raises(ValueError):
        cfg.load_config(str(p))


def test_malformed_yaml_raises_value_error(tmp_path):
    p = tmp_path / "config.yaml"
    # Write malformed YAML (unclosed bracket)
    p.write_text("domain: est.com.kz\ncourse_name: [unclosed")
    with pytest.raises(ValueError) as e:
        cfg.load_config(str(p))
    assert "парсинга" in str(e.value)
