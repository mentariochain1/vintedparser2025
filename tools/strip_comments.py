#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Iterable, Iterator

import tokenize


@dataclass
class FileChange:
    path: Path
    original: str
    updated: str
    changed: bool
    details: str = ""


PY_EXTS = {".py"}
HTML_EXTS = {".html", ".htm"}
CSS_EXTS = {".css"}
JS_EXTS = {".js"}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    "supabase/migrations",
}


def iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    for base in paths:
        if base.is_file():
            yield base
            continue
        for root, dirs, files in os.walk(base):
            # prune skip dirs
            pruned: list[str] = []
            for d in list(dirs):
                rel = os.path.relpath(os.path.join(root, d), start=base)
                if d in SKIP_DIRS or any(rel.startswith(skip) for skip in SKIP_DIRS):
                    pruned.append(d)
            for d in pruned:
                dirs.remove(d)

            for name in files:
                p = Path(root) / name
                yield p


def read_text(path: Path, is_python: bool) -> str:
    if is_python:
        # Preserve declared encoding
        with tokenize.open(path) as f:  # type: ignore[attr-defined]
            return f.read()
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str, is_python: bool) -> None:
    # Try to preserve newline style by inspecting original
    newline = None
    try:
        with open(path, "rb") as f:
            data = f.read()
        if b"\r\n" in data:
            newline = "\r\n"
    except Exception:
        pass
    path.write_text(text, encoding="utf-8", newline=newline)


def strip_python_comments(source: str) -> tuple[str, int]:
    tokens = tokenize.tokenize(BytesIO(source.encode("utf-8")).readline)
    out: list[tuple[int, str]] = []
    removed = 0
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            removed += 1
            continue
        if tok.type == tokenize.NL and out and out[-1][0] == tokenize.NL:
            # collapse excessive blank lines
            continue
        # Keep everything else (ENCODING, NEWLINE, INDENT, DEDENT, NAME, STRING, etc.)
        out.append((tok.type, tok.string))
    text = tokenize.untokenize(out)
    # In Py3.12, untokenize returns str
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    # Trim trailing whitespace
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    return text, removed


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_CSS_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_JS_LINE_RE = re.compile(r"(?m)^[ \t]*//.*$")


def strip_html_comments(source: str) -> tuple[str, int]:
    new, n = _HTML_COMMENT_RE.subn("", source)
    return new, n


def strip_css_comments(source: str) -> tuple[str, int]:
    new, n = _CSS_BLOCK_RE.subn("", source)
    return new, n


def strip_js_comments(source: str) -> tuple[str, int]:
    # Conservative: remove block comments everywhere and full-line // comments
    new, n1 = _CSS_BLOCK_RE.subn("", source)
    new2, n2 = _JS_LINE_RE.subn("", new)
    # remove leftover blank lines from removed line comments
    new2 = re.sub(r"(?m)^[ \t]*\n", "\n", new2)
    return new2, n1 + n2


def process_file(path: Path) -> FileChange | None:
    ext = path.suffix.lower()
    if ext not in PY_EXTS | HTML_EXTS | CSS_EXTS | JS_EXTS:
        return None

    is_python = ext in PY_EXTS
    try:
        original = read_text(path, is_python=is_python)
    except Exception as e:
        return FileChange(path, "", "", False, details=f"read error: {e}")

    stripper: Callable[[str], tuple[str, int]]
    kind = ""
    if ext in PY_EXTS:
        stripper = strip_python_comments
        kind = "python"
    elif ext in HTML_EXTS:
        stripper = strip_html_comments
        kind = "html"
    elif ext in CSS_EXTS:
        stripper = strip_css_comments
        kind = "css"
    else:
        stripper = strip_js_comments
        kind = "js"

    try:
        updated, removed = stripper(original)
    except Exception as e:
        return FileChange(path, original, original, False, details=f"strip error ({kind}): {e}")

    details = f"removed={removed} kind={kind}"
    return FileChange(path, original, updated, updated != original, details=details)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Strip comments from code files")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("src"), Path("tests"), Path("gunicorn_conf.py")],
        help="Files or directories to process",
    )
    parser.add_argument(
        "--include",
        default="py",
        help="Comma-separated kinds to include: py,html,css,js (default: py)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes in-place. Default is dry-run (report only)",
    )

    args = parser.parse_args(argv)

    include = {k.strip().lower() for k in args.include.split(",") if k.strip()}
    global PY_EXTS, HTML_EXTS, CSS_EXTS, JS_EXTS

    exts: set[str] = set()
    if "py" in include:
        exts |= PY_EXTS
    if "html" in include:
        exts |= HTML_EXTS
    if "css" in include:
        exts |= CSS_EXTS
    if "js" in include:
        exts |= JS_EXTS

    total = 0
    changed = 0
    removed_sum = 0
    failures: list[FileChange] = []
    changed_files: list[FileChange] = []

    files: list[Path] = []
    for p in args.paths:
        if p.exists():
            files.extend([f for f in iter_files([p]) if f.suffix.lower() in exts])

    for f in sorted(set(files)):
        total += 1
        fc = process_file(f)
        if fc is None:
            continue
        if fc.details.startswith("read error") or fc.details.startswith("strip error"):
            failures.append(fc)
            continue
        if fc.changed:
            changed += 1
            # parse removed count from details
            try:
                removed = int(fc.details.split("removed=")[1].split()[0])
            except Exception:
                removed = 0
            removed_sum += removed
            changed_files.append(fc)
            if args.apply:
                write_text(f, fc.updated, is_python=f.suffix.lower() in PY_EXTS)

    if not args.apply:
        print(f"Dry-run: scanned={total} changed={changed} comments_removed≈{removed_sum}")
        for fc in changed_files:
            print(f" - {fc.path} ({fc.details})")
    else:
        print(f"Applied: scanned={total} changed={changed} comments_removed≈{removed_sum}")

    if failures:
        print("Failures:")
        for fc in failures:
            print(f" - {fc.path}: {fc.details}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:])) 