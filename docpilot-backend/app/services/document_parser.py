from io import BytesIO
from docx import Document as DocDocument
from pypdf import PdfReader


def parse_txt_or_md(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")


def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    texts: list[str] = []

    for page in reader.pages:
        texts.append(page.extract_text() or "")

    return "\n".join(texts).strip()

def parse_docx(file_bytes: bytes) -> str:
    doc = DocDocument(BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs]).strip()


def parse_document(filename: str, file_bytes: bytes) -> str:
    lower_name = filename.lower()

    if lower_name.endswith((".txt", ".md")):
        return parse_txt_or_md(file_bytes)

    if lower_name.endswith(".pdf"):
        return parse_pdf(file_bytes)
    
    if lower_name.endswith(".docx"):
        return parse_docx(file_bytes)

    raise ValueError(
        "Unsupported file type. Only pdf, docx, txt and md are supported."
    )