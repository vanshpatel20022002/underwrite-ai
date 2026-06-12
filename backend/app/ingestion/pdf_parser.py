from pathlib import Path

import fitz


def extract_pdf_chunks(path: str, doc_type: str) -> list[dict]:
    chunks: list[dict] = []
    doc = fitz.open(path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if not text:
            continue
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            if len(para) < 30:
                continue
            chunks.append(
                {
                    "doc_type": doc_type,
                    "page": page_num + 1,
                    "section": f"paragraph_{i + 1}",
                    "content": para,
                    "source_file": Path(path).name,
                }
            )
    doc.close()
    return chunks
