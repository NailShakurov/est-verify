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
