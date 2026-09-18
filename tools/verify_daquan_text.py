#!/usr/bin/env python3
"""Verify and layer Da Liu Ren Da Quan text from the source PDF."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "六壬vault"
BOOK_DIR = ROOT.parents[1] / "books" / "六壬"
SECOND_VOLUME = VAULT / "10-底本" / "六壬大全" / "02-第二册 十二神将"
PAGE_RE = re.compile(r"^页:\s*(\d+)-(\d+)\s*$", re.MULTILINE)
BODY_RE = re.compile(r"\n## 原刻正文\n.*\Z", re.DOTALL)
LAYERED_BODY_RE = re.compile(r"\n## 原刻正文（据PDF文字层分层）\n.*\Z", re.DOTALL)


def find_pdf() -> Path:
    matches = sorted(BOOK_DIR.glob("六壬大全*.pdf"))
    if len(matches) != 1:
        raise SystemExit(f"Expected one 六壬大全 PDF under {BOOK_DIR}, found {len(matches)}")
    return matches[0]


def page_lines(page: fitz.Page) -> list[list[dict]]:
    lines = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            spans = [span for span in line["spans"] if span["text"].strip()]
            if not spans:
                continue
            if all(round(span["size"], 1) == 9.0 for span in spans):
                continue
            text = "".join(span["text"] for span in spans).strip()
            if re.fullmatch(r"\d+", text):
                continue
            lines.append(spans)
    return lines


def printed_page_number(page: fitz.Page) -> str:
    candidates = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if re.fullmatch(r"\d+", text):
                candidates.append((line["bbox"][1], text))
    return max(candidates, default=(0, "?"))[1]


def span_kind(span: dict) -> str:
    size = round(span["size"], 1)
    if size >= 14.0:
        return "main"
    if size >= 10.0:
        return "note"
    return "meta"


def render_mixed_line(spans: list[dict]) -> str:
    chunks: list[str] = []
    note_buffer: list[str] = []

    def flush_note() -> None:
        if note_buffer:
            chunks.append(f"〔夹注：{''.join(note_buffer).strip()}〕")
            note_buffer.clear()

    for span in spans:
        text = span["text"]
        if span_kind(span) == "note":
            note_buffer.append(text)
        else:
            flush_note()
            chunks.append(text)
    flush_note()
    return "".join(chunks).strip()


def render_pages(document: fitz.Document, first: int, last: int) -> str:
    output = [
        "## 原刻正文（据PDF文字层分层）",
        "",
        "> 字号层级已据原书PDF核对：大字为正文；行内小字标作 `〔夹注：……〕`；",
        "> 全页小字另列“原刻小字注解”。仍须结合影像逐页抽查字形与错简。",
        "",
    ]
    for page_number in range(first, last + 1):
        page = document[page_number - 1]
        lines = page_lines(page)
        has_main = any(
            span_kind(span) == "main" for line in lines for span in line
        )
        printed = printed_page_number(page)
        output.append(f"### PDF页 {page_number}（书内页码 {printed}）")
        output.append("")
        if not has_main:
            output.append("#### 原刻小字注解")
            output.append("")
            output.extend("".join(span["text"] for span in line).strip() for line in lines)
        else:
            output.extend(render_mixed_line(line) for line in lines)
        output.append("")
    return "\n".join(output).rstrip() + "\n"


def update_entry(path: Path, document: fitz.Document) -> None:
    current = path.read_text(encoding="utf-8")
    match = PAGE_RE.search(current)
    if not match:
        raise ValueError(f"Missing page range: {path}")
    first, last = map(int, match.groups())
    rendered = render_pages(document, first, last)
    printed_first = printed_page_number(document[first - 1])
    printed_last = printed_page_number(document[last - 1])
    if "影像核对:" not in current:
        current = current.replace(
            "状态:",
            "影像核对: 字号分层已据PDF核对\n状态:",
            1,
        )
    if "书内页码:" not in current:
        current = current.replace(
            f"页: {first}-{last}",
            f"页: {first}-{last}\n书内页码: {printed_first}-{printed_last}",
            1,
        )
    current = current.replace(
        f"原书页 {first}-{last}",
        f"PDF页 {first}-{last}｜书内页码 {printed_first}-{printed_last}",
        1,
    )
    body_pattern = LAYERED_BODY_RE if LAYERED_BODY_RE.search(current) else BODY_RE
    if not body_pattern.search(current):
        raise ValueError(f"Missing 原刻正文 section: {path}")
    updated = body_pattern.sub("\n" + rendered, current)
    path.write_text(updated, encoding="utf-8", newline="\n")


def render_page_image(document: fitz.Document, page_number: int) -> Path:
    output_dir = ROOT / "sources" / "六壬大全影像页"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"p{page_number:03d}.png"
    pixmap = document[page_number - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pixmap.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry", help="Entry filename stem to print or update")
    parser.add_argument("--write-second-volume", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--render-page", type=int)
    args = parser.parse_args()

    pdf = find_pdf()
    document = fitz.open(pdf)
    if args.render_page:
        output = render_page_image(document, args.render_page)
        print(output)
        return
    if args.write_second_volume:
        paths = sorted(SECOND_VOLUME.glob("*.md"))
        for path in paths:
            update_entry(path, document)
            print(f"updated {path.relative_to(ROOT)}")
        return

    if not args.entry:
        parser.error("provide --entry or --write-second-volume")
    matches = list(SECOND_VOLUME.glob(f"*{args.entry}*.md"))
    if len(matches) != 1:
        raise SystemExit(f"Expected one entry match, found {len(matches)}")
    path = matches[0]
    if args.write:
        update_entry(path, document)
        print(f"updated {path.relative_to(ROOT)}")
    else:
        current = path.read_text(encoding="utf-8")
        match = PAGE_RE.search(current)
        if not match:
            raise SystemExit(f"Missing page range: {path}")
        print(render_pages(document, *map(int, match.groups())))


if __name__ == "__main__":
    main()
