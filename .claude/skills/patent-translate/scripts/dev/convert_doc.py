#!/usr/bin/env python3
"""Convert a legacy binary .doc source into .docx via LibreOffice headless.

python-docx cannot read the OLE2 .doc format, so a .doc source must be
converted before ingest. LibreOffice is used because it preserves paragraph
and heading structure (plain-text extractors like antiword/catdoc destroy the
segmentation the pipeline depends on). This is a lossy step in principle: after
converting, always verify the .docx segmentation against the source before
trusting it (paragraph count, headings, claims, reference numerals).

Usage:
    convert_doc.py --project projects/<slug> [--source name.doc] [--keep-doc]

Writes <slug>/source.docx next to the .doc. Refuses to overwrite an existing
source.docx unless --force. The original .doc is left in place (it is the
authoritative artifact) unless --keep-doc is omitted AND --force is given, in
which case it is still kept — we never delete the source.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def find_soffice() -> str:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    die(
        "LibreOffice not found (need 'soffice' or 'libreoffice' on PATH). "
        "Install libreoffice-writer to convert .doc sources."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a .doc source to .docx via LibreOffice.")
    ap.add_argument("--project", required=True, help="Project dir, e.g. projects/acme")
    ap.add_argument("--source", help="Explicit .doc filename inside the project dir")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing source.docx")
    args = ap.parse_args()

    project = Path(args.project)
    if not project.is_dir():
        die(f"project dir not found: {project}")

    if args.source:
        src = project / args.source
        if not src.is_file():
            die(f"source not found: {src}")
    else:
        docs = sorted(p for p in project.glob("*.doc") if p.suffix.lower() == ".doc")
        if not docs:
            die(f"no .doc file in {project} (pass --source)")
        if len(docs) > 1:
            die(f"multiple .doc files in {project}; pass --source to pick one: {[d.name for d in docs]}")
        src = docs[0]

    target = project / "source.docx"
    if target.exists() and not args.force:
        die(f"{target} already exists; pass --force to overwrite")

    soffice = find_soffice()
    # LibreOffice writes <src-stem>.docx into --outdir; we then rename to source.docx.
    cmd = [
        soffice, "--headless", "--convert-to",
        "docx:MS Word 2007 XML", "--outdir", str(project), str(src),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        die("LibreOffice conversion timed out after 300s")
    if proc.returncode != 0:
        die(f"LibreOffice failed (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}")

    produced = project / (src.stem + ".docx")
    if not produced.is_file():
        die(f"conversion reported success but {produced} was not created:\n{proc.stdout}")
    if produced.resolve() != target.resolve():
        if target.exists():
            target.unlink()
        produced.rename(target)

    print(f"Converted {src.name} -> {target}")
    print("NEXT: verify segmentation with ingest.py, then read every segment against the .doc.")


if __name__ == "__main__":
    main()
