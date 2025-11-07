import io

import pytest
from werkzeug.datastructures import FileStorage

from services.form_autofill import analyze_sat_upload


def _make_filestorage(content: bytes, filename: str, content_type: str = "text/plain") -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename, content_type=content_type)


def test_analyze_sat_upload_detects_digital_signals_from_csv():
    csv_content = (
        "Signal TAG,Description,Result\n"
        "PMP-101,Start command acknowledged,PASS\n"
        "PMP-102,Stop command acknowledged,PASS\n"
    )
    storage = _make_filestorage(csv_content.encode("utf-8"), "tag_list.csv", "text/csv")

    result = analyze_sat_upload(storage)

    assert "DIGITAL_SIGNALS" in result.table_updates
    rows = result.table_updates["DIGITAL_SIGNALS"]
    assert len(rows) == 2
    assert rows[0]["Signal_TAG"] == "PMP-101"
    assert rows[0]["Result"] == "PASS"


def test_analyze_sat_upload_extracts_scope_from_docx(tmp_path):
    pytest.importorskip("docx")
    from docx import Document  # type: ignore

    doc_path = tmp_path / "scope.docx"
    document = Document()
    document.add_paragraph("Scope: This SAT covers the booster pump station automation upgrades.")
    document.save(doc_path)

    storage = _make_filestorage(
        doc_path.read_bytes(),
        "Scope.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    result = analyze_sat_upload(storage)

    assert result.field_updates["SCOPE"].startswith("Scope: This SAT covers")
