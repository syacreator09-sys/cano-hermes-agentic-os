from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
files = []
for path in sorted(ROOT.rglob("*")):
    if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
(ROOT / "BUILD_MANIFEST.json").write_text(
    json.dumps({"files": files, "count": len(files)}, indent=2), encoding="utf-8"
)
print(len(files))
