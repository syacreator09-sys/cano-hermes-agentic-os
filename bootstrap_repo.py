#!/usr/bin/env python3
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from bootstrap_catalog_std import generate
from bootstrap_files_01 import FILES as FILES_1
from bootstrap_files_02 import FILES as FILES_2
from bootstrap_files_03 import FILES as FILES_3
from bootstrap_files_04 import FILES as FILES_4
from bootstrap_files_05 import FILES as FILES_5
from bootstrap_files_06 import FILES as FILES_6
from bootstrap_files_07_10 import FILES as FILES_7_10
from bootstrap_files_11_13 import FILES as FILES_11_13
from bootstrap_files_14_15 import FILES as FILES_14_15

BOOTSTRAP_NAMES = {
    "bootstrap_repo.py", "bootstrap_catalog.py", "bootstrap_catalog_std.py",
    "bootstrap_files_01.py", "bootstrap_files_02.py", "bootstrap_files_03.py",
    "bootstrap_files_04.py", "bootstrap_files_05.py", "bootstrap_files_06.py",
    "bootstrap_files_07_10.py", "bootstrap_files_11_13.py", "bootstrap_files_14_15.py",
}


def main(force: bool = False) -> None:
    root = Path(__file__).resolve().parent
    if force:
        for name in ("src", "agents", "skills", "scripts", "tests", "docs", "vault",
                     "infrastructure", "generated", "runtime"):
            shutil.rmtree(root / name, ignore_errors=True)
    for mapping in (FILES_1, FILES_2, FILES_3, FILES_4, FILES_5, FILES_6,
                    FILES_7_10, FILES_11_13, FILES_14_15):
        for relative, content in mapping.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    generate(root)
    shutil.rmtree(root / ".bootstrap", ignore_errors=True)
    for name in BOOTSTRAP_NAMES:
        (root / name).unlink(missing_ok=True)
    print("Materialized Cano Hermes Agentic OS v0.2.0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    main(args.force)
