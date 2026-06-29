#!/usr/bin/env python3
"""Copy docs into a markdown-only tree.

Files under the source docs directory are copied into the destination directory.
Files ending in .mdx are written with a .md extension; all other files keep
their original names.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def output_path(source_root: Path, destination_root: Path, source_file: Path) -> Path:
    relative_path = source_file.relative_to(source_root)
    if source_file.suffix == ".mdx":
        relative_path = relative_path.with_suffix(".md")
    return destination_root / relative_path


def copy_docs(source_root: Path, destination_root: Path, clean: bool) -> tuple[int, int]:
    source_root = source_root.resolve()
    destination_root = destination_root.resolve()

    if not source_root.is_dir():
        raise SystemExit(f"Source directory does not exist: {source_root}")

    if source_root == destination_root or source_root in destination_root.parents:
        raise SystemExit("Destination must not be the source directory or inside it.")

    if clean and destination_root.exists():
        shutil.rmtree(destination_root)

    seen_outputs: dict[Path, Path] = {}
    source_files = [path for path in source_root.rglob("*") if path.is_file()]

    for source_file in source_files:
        target_file = output_path(source_root, destination_root, source_file)
        previous_source = seen_outputs.get(target_file)
        if previous_source is not None:
            raise SystemExit(
                "Output path collision:\n"
                f"  {previous_source}\n"
                f"  {source_file}\n"
                f"Both map to {target_file}"
            )
        seen_outputs[target_file] = source_file

    renamed_count = 0
    for source_file in source_files:
        target_file = output_path(source_root, destination_root, source_file)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)
        if source_file.suffix == ".mdx":
            renamed_count += 1

    return len(source_files), renamed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy docs to docs-md, renaming .mdx files to .md."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("docs"),
        help="Source docs directory. Defaults to docs.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("docs-md"),
        help="Destination directory. Defaults to docs-md.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the destination directory before copying.",
    )

    args = parser.parse_args()
    copied_count, renamed_count = copy_docs(args.source, args.dest, args.clean)
    print(
        f"Copied {copied_count} files to {args.dest}; "
        f"renamed {renamed_count} .mdx files to .md."
    )


if __name__ == "__main__":
    main()
