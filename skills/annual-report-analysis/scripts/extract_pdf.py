"""Extract numbered text, optional table candidates and original-page images."""
import argparse
import hashlib
import json
from pathlib import Path

import pdfplumber


def extract(path, output, pages=None, tables=False, render_dir=None):
    path, output = Path(path), Path(output)
    selected = set(pages) if pages else None
    if render_dir is not None:
        render_dir = Path(render_dir)
        render_dir.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(path) as pdf:
        if selected and (min(selected) < 1 or max(selected) > len(pdf.pages)):
            raise ValueError("page numbers are one-based and must be inside the PDF")
        records = []
        for i, page in enumerate(pdf.pages, 1):
            if selected is not None and i not in selected:
                continue
            text = page.extract_text() or ""
            record = {"pdf_page": i, "text": text,
                      "status": "text_extracted_needs_review" if text.strip() else "requires_ocr_or_visual_review"}
            if tables:
                # Wide, unstroked fills can create false borders; retain thin grid rectangles.
                view = page.filter(lambda obj: not (obj["object_type"] == "rect" and obj["fill"]
                    and not obj["stroke"] and obj["width"] > 1 and obj["height"] > 1))
                record["table_method"] = "line candidates excluding unstroked filled rectangles wider and taller than 1pt"
                record["table_status"] = "candidates_require_header_and_visual_review"
                record["tables"] = [{"table": n, "bbox": table.bbox, "rows": table.extract(),
                                     "cell_bboxes": [row.cells for row in table.rows]}
                                    for n, table in enumerate(view.find_tables(), 1)]
            if render_dir is not None:
                image_path = render_dir / f"page-{i:04d}.png"
                page.to_image(resolution=150, antialias=True).save(image_path)
                record["rendered_page"] = str(image_path.resolve())
            records.append(record)
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
    parser.add_argument("--tables", action="store_true", help="Include candidate matrices and cell bounds; verify against the page")
    parser.add_argument("--render", metavar="DIRECTORY", help="Render selected original pages to PNG for visual review")
    args = parser.parse_args()
    result = extract(args.input, args.output, args.pages, args.tables, args.render)
    print(json.dumps({"pages": len(result["pages"]), "sha256": result["sha256"]}))
