import fitz
from shared_types.pipeline import RawBlock


def parse_pdf(file_path: str) -> list[RawBlock]:
    doc = fitz.open(file_path)
    blocks: list[RawBlock] = []
    for page_num, page in enumerate(doc, start=1):
        for block in page.get_text("blocks"):
            text = block[4].strip()
            if text:
                blocks.append(RawBlock(text=text, page=page_num))
    return blocks
