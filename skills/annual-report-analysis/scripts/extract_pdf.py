"""Extract numbered pages; scanned/unreadable pages remain explicit gaps."""
import argparse
import hashlib
import json
from pathlib import Path

import pdfplumber


def extract(path, output, pages=None):
    path, output = Path(path), Path(output)
    selected = set(pages) if pages else None
    with pdfplumber.open(path) as pdf:
        if selected and (min(selected) < 1 or max(selected) > len(pdf.pages)):
            raise ValueError("page numbers are one-based and must be inside the PDF")
        records = []
        for i, page in enumerate(pdf.pages, 1):
            if selected is not None and i not in selected:
                continue
            text = page.extract_text() or ""
            records.append({"pdf_page": i, "text": text,
                            "status": "text_extracted_needs_review" if text.strip() else "requires_ocr_or_visual_review"})
        result = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "page_count": len(pdf.pages), "pages": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pages", nargs="+", type=int)
    args = parser.parse_args()
    result = extract(args.input, args.output, args.pages)
    print(json.dumps({"pages": len(result["pages"]), "sha256": result["sha256"]}))
