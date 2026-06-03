from pathlib import Path

from pypdf import PdfReader


def parse_txt_or_md(file_path: bytes) -> str:
    '''
    解析TXT或MD文件
    '''
    return file_path.decode("utf-8", errors='ignore')


def parse_pdf(file_path: bytes) -> str:
    '''
    解析PDF文件
    '''
    # 创建一个临时文件路径对象，指向当前工作目录下的 temp_upload.pdf
    temp_path = Path("temp_upload.pdf")
    temp_path.write_bytes(file_path)

    try:
        reader = PdfReader(str(temp_path))
        texts: list[str] = []

        for page in reader.pages:
            texts.append(page.extract_text() or "")

        return "".join(texts)

    finally:
        if temp_path.exists():
            temp_path.unlink()


def parse_document(filename: str, file_bytes: bytes) -> str:
    # 判断文件类型并调用相应的解析函数
    lower_name = filename.lower()
    if lower_name.endswith((".txt", ".md")):
        return parse_txt_or_md(file_bytes)
    elif lower_name.endswith(".pdf"):
        return parse_pdf(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {lower_name}")
