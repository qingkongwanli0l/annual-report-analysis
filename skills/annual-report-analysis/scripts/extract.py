"""Extract page-addressable PDF text or located HTML blocks for source review."""

import argparse
import hashlib
import json
from pathlib import Path


def page_numbers(spec, count):
    if not spec:
        return range(1, count + 1)
    selected = set()
    for part in spec.split(","):
        bounds = part.strip().split("-")
        first = int(bounds[0])
        last = int(bounds[1]) if len(bounds) == 2 else first
        if len(bounds) > 2 or first < 1 or last < first or last > count:
            raise ValueError(f"Invalid page range {part}; PDF has {count} pages")
        selected.update(range(first, last + 1))
    return sorted(selected)


def extract(path, pages=None):
    result = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "blocks": []}
    if path.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            result.update(format="pdf", page_count=len(pdf.pages))
            for number in page_numbers(pages, len(pdf.pages)):
                page = pdf.pages[number - 1]
                text = page.extract_text() or ""
                result["blocks"].append({"locator": f"PDF p. {number}", "page": number,
                                         "text": text, "tables": page.extract_tables(),
                                         "needs_visual_review": not text.strip()})
        result["note"] = "PDF page numbers are 1-based file positions, not printed page labels. Verify tables against page images; extraction is not a financial fact checker."
    elif path.suffix.lower() in {".html", ".htm", ".xhtml"}:
        from lxml import html

        if pages:
            raise ValueError("--pages applies only to PDF files")
        document = html.document_fromstring(path.read_bytes())
        for node in document.xpath("//script|//style|//noscript|//head|//*[local-name()='hidden' or name()='ix:hidden' or @hidden]"):
            node.drop_tree()
        tree = document.getroottree()
        for node in document.xpath("//h1|//h2|//h3|//h4|//p[not(ancestor::table)]|//li[not(ancestor::table)]|//table[not(ancestor::table)]"):
            text = " ".join(node.text_content().split())
            if not text:
                continue
            anchor = node.get("id")
            block = {"locator": f"#{anchor}" if anchor else tree.getpath(node), "text": text}
            if node.tag == "table":
                block["rows"] = [[" ".join(cell.text_content().split()) for cell in row.xpath("./th|./td")] for row in node.xpath(".//tr")]
                block["note"] = "Raw cells; merged row/column spans are not normalized. Verify the original table."
            result["blocks"].append(block)
        if not result["blocks"]:
            result["blocks"].append({"locator": "/html/body", "text": document.text_content()})
        result.update(format="html", note="HTML has no reliable PDF pages. Cite document URL plus anchor/XPath and section title. Hidden/XBRL metadata is not a substitute for visible statements.")
    else:
        raise ValueError("Input must be a PDF or saved HTML disclosure")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pages", help="1-based PDF pages, for example 1-3,12")
    args = parser.parse_args()
    try:
        result = extract(args.input, args.pages)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Extraction failed: {error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
