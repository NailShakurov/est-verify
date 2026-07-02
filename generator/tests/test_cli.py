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
font_path: assets/DejaVuSans.ttf
keys:
  private: {keysdir}/priv.key
  public: {keysdir}/pub.key
columns:
  fio: "ФИО"
  date: "Дата выдачи"
  number: "Номер"
placement:
  fio: {{rect: [59, 430, 767, 487], fontsize: 32, color: [0.1, 0.1, 0.5]}}
  date: {{x: 120, y: 828, fontsize: 15, color: [0, 0, 0]}}
  cert_num: {{x: 400, y: 960, fontsize: 13, color: [0.3, 0.3, 0.3]}}
  qr: {{x: 570, y: 800, size: 180}}
  verify_label: {{x: 570, y: 994, fontsize: 15, color: [0.2, 0.2, 0.6]}}
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


def test_missing_template_pdf_batch(tmp_path, capsys):
    """Test that batch mode with missing template_pdf prints clean error and returns 1."""
    table = str(tmp_path / "s.xlsx")
    _make_table(table, [["001", "Иванов Иван", "2026-07-02"]])
    kd = tmp_path / "k"; outdir = tmp_path / "out"
    missing_template = str(tmp_path / "nonexistent.pdf")
    cfg = _write_config(tmp_path, missing_template, table, str(kd), str(outdir))
    # Generate keys first
    generate.main(["--config", cfg, "--genkey"])
    # Run batch mode with missing template
    rc = generate.main(["--config", cfg])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Файл шаблона не найден" in captured.err
    assert "nonexistent.pdf" in captured.err
    assert "Traceback" not in captured.err  # No Python traceback


def test_missing_template_pdf_preview(tmp_path, capsys):
    """Test that preview mode with missing template_pdf prints clean error and returns 1."""
    table = str(tmp_path / "s.xlsx")
    _make_table(table, [["001", "Иванов Иван", "2026-07-02"]])
    kd = tmp_path / "k"; outdir = tmp_path / "out"
    missing_template = str(tmp_path / "nonexistent.pdf")
    cfg = _write_config(tmp_path, missing_template, table, str(kd), str(outdir))
    # Generate keys first
    generate.main(["--config", cfg, "--genkey"])
    # Run preview mode with missing template
    rc = generate.main(["--config", cfg, "--preview", "1"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Файл шаблона не найден" in captured.err
    assert "nonexistent.pdf" in captured.err
    assert "Traceback" not in captured.err  # No Python traceback


def test_missing_font_file(tmp_path, capsys):
    """Test that batch mode with missing font_path prints clean error and returns 1."""
    doc = fitz.open(); doc.new_page(width=595, height=842)
    template = str(tmp_path / "t.pdf"); doc.save(template); doc.close()
    table = str(tmp_path / "s.xlsx")
    _make_table(table, [["001", "Иванов Иван", "2026-07-02"]])
    kd = tmp_path / "k"; outdir = tmp_path / "out"
    missing_font = str(tmp_path / "nonexistent.ttf")
    # Manually write config with missing font file
    cfg_text = f"""
domain: est.com.kz
course_name: "Евразийская школа трекинга"
course_code: "E"
compact_course: false
template_pdf: {template}
table_path: {table}
output_dir: {outdir}
font_path: {missing_font}
keys:
  private: {kd}/priv.key
  public: {kd}/pub.key
columns:
  fio: "ФИО"
  date: "Дата выдачи"
  number: "Номер"
placement:
  fio: {{rect: [59, 430, 767, 487], fontsize: 32, color: [0.1, 0.1, 0.5]}}
  date: {{x: 120, y: 828, fontsize: 15, color: [0, 0, 0]}}
  cert_num: {{x: 400, y: 960, fontsize: 13, color: [0.3, 0.3, 0.3]}}
  qr: {{x: 570, y: 800, size: 180}}
  verify_label: {{x: 570, y: 994, fontsize: 15, color: [0.2, 0.2, 0.6]}}
"""
    cfg_path = str(tmp_path / "config_bad_font.yaml")
    with open(cfg_path, "w") as f:
        f.write(cfg_text)
    # Generate keys first
    generate.main(["--config", cfg_path, "--genkey"])
    # Run batch mode with missing font
    rc = generate.main(["--config", cfg_path])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Файл шрифта не найден" in captured.err
    assert "nonexistent.ttf" in captured.err
    assert "Traceback" not in captured.err  # No Python traceback
