"""
html_embed.py

Extract inline HTML blocks from Trion source code.

Supports:
 - Comment-marked blocks using Trion comments:
     --html-start [key=value ...]
     ...
     --html-end
 - Explicit <html ...>...</html> tag blocks (supports attributes on the opening tag)

Returns a list of dicts:
    {
      "raw": str,           # full block including markers or tags
      "content": str,       # inner HTML (dedented)
      "start_line": int,    # 1-based line where content starts
      "end_line": int,      # 1-based line where content ends
      "meta": dict,         # parsed metadata from marker OR tag attributes
      "type": "marker"|"tag"#
    }

This module is dependency-free and tolerant to mixed usages.
"""

from typing import List, Dict, Any, Tuple
import re
import textwrap
import os

_MARKER_START_RE = re.compile(r'--\s*html-start(?::|\s+)?(.*)$')
_MARKER_END_RE = re.compile(r'--\s*html-end\b')
_TAG_START_RE = re.compile(r'<html\b([^>]*)>', flags=re.IGNORECASE)
_TAG_END_RE = re.compile(r'</html>', flags=re.IGNORECASE)
_ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*"(.*?)"|([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*([^\s">]+)')

def _parse_meta(meta_str: str) -> Dict[str, Any]:
    """
    Parse a simple meta token string like: 'name=foo mode=compact flag'
    into a dict. Flags get value True.
    """
    meta: Dict[str, Any] = {}
    if not meta_str:
        return meta
    tokens = meta_str.strip().split()
    for tok in tokens:
        if '=' in tok:
            k, v = tok.split('=', 1)
            meta[k.strip()] = v.strip().strip('"')
        else:
            meta[tok] = True
    return meta

def _parse_tag_attrs(attr_text: str) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    if not attr_text:
        return attrs
    for m in _ATTR_RE.finditer(attr_text):
        if m.group(1):
            attrs[m.group(1)] = m.group(2)
        elif m.group(3):
            attrs[m.group(3)] = m.group(4)
    return attrs

def extract_html_blocks(code: str) -> List[Dict[str, Any]]:
    """
    Extract HTML blocks from `code`. Supports both marker-style and <html> tags.
    Raises ValueError for unclosed marker-style blocks.
    """
    blocks: List[Dict[str, Any]] = []

    # Normalize line endings and iterate with 1-based line numbers
    lines = code.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    # First pass: marker-style blocks (line-oriented)
    inside = False
    current_lines: List[str] = []
    current_meta: Dict[str, Any] = {}
    content_start_line = 0

    for idx, line in enumerate(lines, start=1):
        m_start = _MARKER_START_RE.search(line)
        if m_start:
            if inside:
                raise ValueError(f"Nested --html-start at line {idx}")
            inside = True
            current_lines = []
            current_meta = _parse_meta(m_start.group(1) or "")
            content_start_line = idx + 1
            continue

        if _MARKER_END_RE.search(line):
            if not inside:
                # stray end marker; ignore
                continue
            inside = False
            content_end_line = idx - 1
            raw = "\n".join(lines[content_start_line - 1: content_end_line])
            content = textwrap.dedent("\n".join(current_lines)).rstrip("\n")
            blocks.append({
                "raw": "\n".join(lines[content_start_line - 2: idx]) if content_start_line >= 2 else ("\n".join(lines[:idx])),
                "content": content,
                "start_line": content_start_line,
                "end_line": content_end_line,
                "meta": current_meta,
                "type": "marker",
            })
            current_lines = []
            current_meta = {}
            content_start_line = 0
            continue

        if inside:
            current_lines.append(line)

    if inside:
        raise ValueError("Unclosed --html-start: missing --html-end before end of file")

    # Second pass: tag-style blocks. We avoid duplicating blocks already captured by markers.
    # We'll scan the full text and track used regions (by line ranges) to skip overlaps.
    used_ranges: List[Tuple[int, int]] = [(b["start_line"], b["end_line"]) for b in blocks]

    text = "\n".join(lines)
    pos = 0
    while True:
        m_tag = _TAG_START_RE.search(text, pos)
        if not m_tag:
            break
        tag_start = m_tag.start()
        attr_text = m_tag.group(1) or ""
        tag_attrs = _parse_tag_attrs(attr_text)
        # find corresponding end tag
        m_end = _TAG_END_RE.search(text, m_tag.end())
        if not m_end:
            # no closing tag; treat as error and stop scanning further tags
            break
        tag_end = m_end.end()
        # compute line numbers
        start_line = text.count("\n", 0, m_tag.end()) + 1  # line where content after '>' may begin
        # position after the '>'
        content_begin_pos = m_tag.end()
        content_end_pos = m_end.start()
        end_line = text.count("\n", 0, content_end_pos) + 1

        # Determine if this range overlaps existing marker-based blocks; if so, skip to avoid duplicates
        overlap = False
        for rstart, rend in used_ranges:
            if not (end_line < rstart or start_line > rend):
                overlap = True
                break
        if not overlap:
            raw_block = text[m_tag.start(): tag_end]
            inner = text[content_begin_pos:content_end_pos]
            content = textwrap.dedent(inner).rstrip("\n")
            blocks.append({
                "raw": raw_block,
                "content": content,
                "start_line": start_line,
                "end_line": end_line,
                "meta": tag_attrs,
                "type": "tag",
            })
            used_ranges.append((start_line, end_line))
        pos = tag_end

    return blocks

def extract_html_blocks_from_file(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    return extract_html_blocks(code)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python html_embed.py <file.trn>")
        raise SystemExit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        print("File not found:", path)
        raise SystemExit(2)
    for i, b in enumerate(extract_html_blocks_from_file(path), start=1):
        meta = " ".join(f'{k}="{v}"' if v is not True else k for k, v in b["meta"].items())
        print(f"Block {i}: type={b['type']} lines={b['start_line']}-{b['end_line']} meta=({meta}) size={len(b['content'])} chars")
        if b['content']:
            print(b['content'])
            print("-" * 40)

