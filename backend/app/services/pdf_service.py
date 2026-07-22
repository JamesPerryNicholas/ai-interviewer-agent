"""PDF text extraction service powered by PyMuPDF."""

from pathlib import Path

import fitz


def extract_pdf_text(file_path: str | Path) -> str:
    """Extract plain text from every page in a PDF file."""

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {path}")

    with fitz.open(path) as document:
        text = "\n".join(page.get_text("text") for page in document)

    return text.strip()

