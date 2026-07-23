"""PDF text extraction service powered by PyMuPDF."""

from pathlib import Path

import fitz

from app.config import settings


class PdfLimitError(ValueError):
    """Raised when a PDF exceeds configured processing limits."""


def extract_pdf_text(
    file_path: str | Path,
    *,
    max_pages: int | None = None,
    max_text_chars: int | None = None,
) -> str:
    """Extract plain text from every page in a PDF file."""

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {path}")

    page_limit = max_pages or settings.max_pdf_pages
    text_limit = max_text_chars or settings.max_resume_text_chars
    with fitz.open(path) as document:
        if document.page_count > page_limit:
            raise PdfLimitError(f"PDF 页数不能超过 {page_limit} 页")
        chunks: list[str] = []
        text_length = 0
        for page in document:
            page_text = page.get_text("text")
            text_length += len(page_text)
            if text_length > text_limit:
                raise PdfLimitError(f"简历文本不能超过 {text_limit} 个字符")
            chunks.append(page_text)
        text = "\n".join(chunks)

    return text.strip()
