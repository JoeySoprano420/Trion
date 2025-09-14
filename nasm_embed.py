"""
nasm_embed.py

Extract inline NASM blocks from Trion source code between markers:
    --nasm-start [opts]
    --nasm-end

Returns a list of dicts with:
    - content: str (dedented NASM source)
    - start_line: int (1-based line number where block content starts)
    - end_line: int (1-based line number where block content ends)
    - meta: dict (parsed options from the start marker; supports key=value and flags)

Example start marker forms:
    --nasm-start
    --nasm-start name=init bits=64
    --nasm-start:label flag

This module is dependency-free and suitable for use in the Trion toolchain.
"""

from typing import Dict, List, Any
import re
import textwrap
import os
import argparse

_START_RE = re.compile(r'--\s*nasm-start(?::|\s+)?(.*)$')
_END_RE = re.compile(r'--\s*nasm-end\b')


def _parse_meta(meta_str: str) -> Dict[str, Any]:
    """
    Parse a metadata string from the start marker into a dict.
    Supports tokens like `key=value` or standalone `flag`.
    """
    meta: Dict[str, Any] = {}
    if not meta_str:
        return meta
    tokens = meta_str.strip().split()
    for tok in tokens:
        if '=' in tok:
            k, v = tok.split('=', 1)
            meta[k.strip()] = v.strip()
        else:
            meta[tok] = True
    return meta


def extract_nasm_blocks(code: str) -> List[Dict[str, Any]]:
    """
    Extract NASM blocks from the provided source `code`.

    Raises:
        ValueError: if a nested start is found or end marker is missing.

    Returns:
        List of dicts with keys: content, start_line, end_line, meta
    """
    blocks: List[Dict[str, Any]] = []
    inside = False
    current_lines: List[str] = []
    current_meta: Dict[str, Any] = {}
    content_start_line: int = 0

    # Normalize line endings and iterate with 1-based line numbers
    lines = code.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for idx, line in enumerate(lines, start=1):
        # check for start marker
        m_start = _START_RE.search(line)
        if m_start:
            if inside:
                raise ValueError(f"Nested --nasm-start at line {idx}")
            inside = True
            current_lines = []
            current_meta = _parse_meta(m_start.group(1) or "")
            content_start_line = idx + 1  # content begins on following line
            continue

        # check for end marker
        if _END_RE.search(line):
            if not inside:
                # stray end; ignore it
                continue
            # finalize block
            inside = False
            content_end_line = idx - 1
            raw = "\n".join(current_lines)
            # dedent to remove common indentation
            content = textwrap.dedent(raw).rstrip("\n")
            blocks.append({
                "content": content,
                "start_line": content_start_line,
                "end_line": content_end_line,
                "meta": current_meta,
            })
            current_lines = []
            current_meta = {}
            content_start_line = 0
            continue

        # accumulate lines if inside
        if inside:
            current_lines.append(line)

    if inside:
        raise ValueError("Unclosed --nasm-start: missing --nasm-end before end of file")

    return blocks


def extract_nasm_blocks_from_file(path: str) -> List[Dict[str, Any]]:
    """
    Convenience helper: read a file and extract NASM blocks.
    """
    with open(path, "r", encoding="utf-8") as fh:
        code = fh.read()
    return extract_nasm_blocks(code)


if __name__ == "__main__":
    # CLI: print summaries, optionally dump contents or write blocks to files
    parser = argparse.ArgumentParser(description="Extract inline NASM blocks from a Trion source file.")
    parser.add_argument("path", help="Trion source file (.trn)")
    parser.add_argument("--dump", action="store_true", help="Print full content of each extracted NASM block")
    parser.add_argument("--write-blocks", action="store_true", help="Write each NASM block to separate .nasm files")
    parser.add_argument("--out-dir", default=".", help="Directory to write extracted blocks when --write-blocks is used")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print("File not found:", args.path)
        raise SystemExit(2)

    try:
        blocks = extract_nasm_blocks_from_file(args.path)
    except Exception as ex:
        print("Error extracting NASM blocks:", ex)
        raise

    base_name = os.path.splitext(os.path.basename(args.path))[0]
    for i, b in enumerate(blocks, start=1):
        meta = " ".join(f"{k}={v}" if v is not True else k for k, v in b["meta"].items())
        print(f"Block {i}: lines {b['start_line']}-{b['end_line']} meta=({meta}) size={len(b['content'])} bytes")
        if args.dump:
            print("---- BEGIN BLOCK ----")
            print(b["content"])
            print("----  END BLOCK  ----")
        if args.write_blocks:
            os.makedirs(args.out_dir, exist_ok=True)
            # prefer meta name if provided, else numbered file
            name_hint = b["meta"].get("name") if isinstance(b["meta"].get("name"), str) else None
            out_filename = f"{base_name}.{name_hint or 'nasm'}.{i}.asm"
            out_path = os.path.join(args.out_dir, out_filename)
            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(b["content"])
            print(f"Wrote block {i} to {out_path}")
