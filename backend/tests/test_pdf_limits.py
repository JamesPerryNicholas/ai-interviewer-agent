"""PDF page and extracted-text safety limit tests."""

import fitz
import pytest

from app.services.pdf_service import PdfLimitError, extract_pdf_text


def _write_pdf(path, pages: list[str]):
    document = fitz.open()
    for content in pages:
        page = document.new_page()
        page.insert_text((72, 72), content)
    document.save(path)
    document.close()


def test_pdf_page_limit(tmp_path):
    path = tmp_path / "pages.pdf"
    _write_pdf(path, ["one", "two"])
    with pytest.raises(PdfLimitError, match="页数"):
        extract_pdf_text(path, max_pages=1, max_text_chars=1000)


def test_pdf_text_limit(tmp_path):
    path = tmp_path / "text.pdf"
    _write_pdf(path, ["this resume text is too long"])
    with pytest.raises(PdfLimitError, match="文本"):
        extract_pdf_text(path, max_pages=5, max_text_chars=5)
