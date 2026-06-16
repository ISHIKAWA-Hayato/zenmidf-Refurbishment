#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path


ICON_REL_RE = re.compile(
    r"<link\b[^>]*\brel\s*=\s*(['\"])icon\1[^>]*>",
    re.IGNORECASE,
)
HREF_RE = re.compile(r"\bhref\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)


def calculate_expected_favicon_href(html_root: Path, html_file: Path) -> str | None:
    rel = html_file.relative_to(html_root)
    parts = rel.parts

    if len(parts) == 1 and html_file.suffix.lower() == ".html":
        return "images/fav.png"

    if (
        len(parts) == 3
        and parts[0] == "station-individual"
        and parts[1] != "99-Others"
        and html_file.suffix.lower() == ".html"
    ):
        return "../../images/fav.png"

    if (
        len(parts) == 4
        and parts[0] == "station-individual"
        and parts[1] == "99-Others"
        and html_file.suffix.lower() == ".html"
    ):
        return "../../../images/fav.png"

    return None


def update_icon_href(content: str, expected_href: str) -> tuple[str, bool]:
    changed = False

    def replace_tag(match: re.Match[str]) -> str:
        nonlocal changed
        tag = match.group(0)

        href_match = HREF_RE.search(tag)
        if not href_match:
            return tag

        current_href = href_match.group(2)
        if current_href == expected_href:
            return tag

        changed = True
        quote = href_match.group(1)
        replacement = f"href={quote}{expected_href}{quote}"
        return HREF_RE.sub(replacement, tag, count=1)

    updated = ICON_REL_RE.sub(replace_tag, content)
    return updated, changed


def collect_target_html_files(html_root: Path) -> list[Path]:
    html_files: list[Path] = []

    for file in sorted(html_root.rglob("*.html")):
        if calculate_expected_favicon_href(html_root, file) is not None:
            html_files.append(file)

    return html_files


def generate_favicon_patch(repo_root: Path, apply_changes: bool) -> str:
    html_root = repo_root / "html"
    if not html_root.is_dir():
        raise FileNotFoundError(f"html directory not found: {html_root}")

    patch_chunks: list[str] = []
    targets = collect_target_html_files(html_root)

    for file in targets:
        expected_href = calculate_expected_favicon_href(html_root, file)
        if expected_href is None:
            continue

        original = file.read_text(encoding="utf-8")
        updated, changed = update_icon_href(original, expected_href)
        if not changed:
            continue

        relpath = file.relative_to(repo_root).as_posix()
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{relpath}",
            tofile=f"b/{relpath}",
        )
        patch_chunks.append("".join(diff))

        if apply_changes:
            file.write_text(updated, encoding="utf-8")

    return "".join(patch_chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate unified diff for favicon href fixes to html/images/fav.png "
            "across the 3 supported html layout patterns."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the same changes to files in addition to printing diff",
    )
    parser.add_argument(
        "--output",
        help="Write unified diff to file instead of stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    try:
        patch_text = generate_favicon_patch(repo_root, apply_changes=args.apply)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not patch_text:
        print("No favicon href changes needed for the supported patterns.")
        return 0

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.write_text(patch_text, encoding="utf-8")
    else:
        print(patch_text, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
