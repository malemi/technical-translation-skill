#!/usr/bin/env python3
"""Edition check for the normative sources the style guide cites.

Usage:
    review_sources.py verify-manifest [--manifest path]   (offline)
    review_sources.py check [--manifest path]             (network)

Repo-level, no --project: the manifest and the style guide are repo files, not
project state. Neither subcommand writes anything.

`verify-manifest` asserts that references/review_sources.json and the `## Sources`
section of references/style-guide.md still describe the same set of texts, one to
one, and that every edition the manifest claims the guide states is literally in
that section. Offline, deterministic, and the part `dev/smoke.py` can assert.

`check` runs those assertions first and then fetches every manifest URL once,
reporting whether the expected edition token is still present. It is a smoke
alarm, not an audit: exit 3 means "the world moved, or we could not look", and
the caller records the report VERBATIM in REVIEW.md and proceeds with the review.
A firing check triggers the separate deep re-audit of the normative layer.

Offline is never a silent pass. With no network every entry is an ERROR line
carrying the exception class and message, the summary counts them, and the exit
code is 3 — there is no cached body, no retry and no fallback anywhere in here.

Exit codes: 0 every entry OK; 1 a broken manifest (a repo defect, which stops the
run); 3 at least one MISSING or ERROR entry.

Run from the repo root.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import requests

# The manifest and the guide are repo files next to this script's package:
# resolve them from the script location so the check can never run against a
# different guide than the one this skill ships.
REFERENCES = Path(__file__).resolve().parent.parent / "references"
MANIFEST_PATH = REFERENCES / "review_sources.json"
STYLE_GUIDE_PATH = REFERENCES / "style-guide.md"

MANIFEST_LABEL = "review_sources.json"
GUIDE_LABEL = "style-guide.md"
SOURCES_HEADING = "## Sources"

REQUIRED_KEYS = ("id", "name", "url", "edition_token")
OPTIONAL_KEYS = ("style_guide_url", "style_guide_edition", "note")
ALLOWED_KEYS = frozenset(REQUIRED_KEYS + OPTIONAL_KEYS)
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# URLs in the guide are written as Markdown autolinks, <https://…>, sometimes
# followed by a comma or a full stop: stop at the bracket and shed trailing
# sentence punctuation.
URL_RE = re.compile(r"https?://[^\s<>()\[\],]+")
_URL_TRAILING = ".,;:"

# One GET per entry, no retries: a slow source must not hold up a review run.
FETCH_TIMEOUT = 20


# --------------------------------------------------------------------------
# inputs


def _load_manifest(path: Path):
    """(parsed document, violations). None document when it could not be read.

    A missing or unparseable manifest is reported as a violation and never
    raised: `check` needs the same failure shape as `verify-manifest`, and both
    exit 1 on it.
    """
    if not path.is_file():
        return None, [f"{MANIFEST_LABEL} file not found: {path}"]
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), []
    except json.JSONDecodeError as exc:
        return None, [f"{MANIFEST_LABEL} invalid JSON: {exc}"]
    except UnicodeDecodeError as exc:
        return None, [f"{MANIFEST_LABEL} not valid UTF-8: {exc}"]


def sources_section(guide_path: Path):
    """(text of the guide's `## Sources` section, violations).

    The section runs from the heading line to the end of the file, per
    CONTRACTS.md. None when the guide is unreadable or has no such heading.
    """
    if not guide_path.is_file():
        return None, [f"{GUIDE_LABEL} file not found: {guide_path}"]
    try:
        text = guide_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return None, [f"{GUIDE_LABEL} not valid UTF-8: {exc}"]
    match = re.search(rf"^{re.escape(SOURCES_HEADING)}\s*$", text, re.MULTILINE)
    if match is None:
        return None, [
            f"{GUIDE_LABEL} has no '{SOURCES_HEADING}' heading: the manifest "
            "cannot be checked against it"
        ]
    return text[match.start():], []


def section_urls(section: str) -> list[str]:
    """Every http(s) URL in the section, in order of appearance, duplicates kept."""
    return [match.group(0).rstrip(_URL_TRAILING) for match in URL_RE.finditer(section)]


# --------------------------------------------------------------------------
# the offline assertion


def manifest_violations(manifest_path, guide_path) -> list[str]:
    """Violations of the manifest against the guide's Sources section.

    Pure: reads two files, prints nothing, never exits, returns one string per
    violation, each already shaped as `<source id or "review_sources.json">
    <detail>`. An empty list means the two files agree.
    """
    manifest_path = Path(manifest_path)
    guide_path = Path(guide_path)
    violations: list[str] = []

    document, load_errors = _load_manifest(manifest_path)
    violations.extend(load_errors)

    section, guide_errors = sources_section(guide_path)
    violations.extend(guide_errors)

    if document is None:
        return violations
    if not isinstance(document, dict):
        violations.append(
            f"{MANIFEST_LABEL} expected a JSON object at the top level, "
            f"got {type(document).__name__}"
        )
        return violations

    sources = document.get("sources")
    if not isinstance(sources, list):
        violations.append(f"{MANIFEST_LABEL} sources is missing or not a list")
        return violations
    if not sources:
        violations.append(f"{MANIFEST_LABEL} sources is empty")
        return violations

    seen_ids: dict[str, int] = {}
    seen_urls: dict[str, str] = {}
    # style_guide_url -> the ids claiming it, for the one-to-one test below.
    claimed: dict[str, list[str]] = {}

    for index, entry in enumerate(sources):
        violations.extend(
            _entry_violations(entry, index, seen_ids, seen_urls, claimed, section)
        )

    if section is not None:
        for url in section_urls(section):
            ids = claimed.get(url, [])
            if not ids:
                violations.append(
                    f"{MANIFEST_LABEL} {GUIDE_LABEL} cites {url} in "
                    f"'{SOURCES_HEADING}' but no manifest entry claims it: add an "
                    "entry or stop citing the source"
                )
            elif len(ids) > 1:
                violations.append(
                    f"{MANIFEST_LABEL} {url} is claimed by {len(ids)} entries "
                    f"({', '.join(ids)}): the mapping to '{SOURCES_HEADING}' must "
                    "be one to one"
                )
    return violations


def _entry_violations(entry, index: int, seen_ids: dict, seen_urls: dict,
                      claimed: dict, section) -> list[str]:
    """Violations of one manifest entry. `seen_ids`, `seen_urls` and `claimed`
    are updated in place; `section` is None when the guide could not be read,
    which skips the two checks that need it."""
    if not isinstance(entry, dict):
        return [f"{MANIFEST_LABEL} sources[{index}] is not an object"]

    out: list[str] = []
    ident = entry.get("id")
    if isinstance(ident, str) and ident.strip():
        locus, prefix = ident.strip(), ""
    else:
        locus, prefix = MANIFEST_LABEL, f"sources[{index}] "

    def fail(detail: str) -> None:
        out.append(f"{locus} {prefix}{detail}")

    # Unknown keys are violations rather than ignored extras: a manifest whose
    # "style_guide_editon" is a typo would silently lose the teeth of the
    # edition assertion, which is the whole point of the file.
    allowed = ", ".join(sorted(ALLOWED_KEYS))
    for key in sorted(set(entry) - ALLOWED_KEYS):
        fail(f"unknown key {key!r} (allowed: {allowed})")

    for key in REQUIRED_KEYS:
        value = entry.get(key)
        if key not in entry:
            fail(f"missing required key {key!r}")
        elif not isinstance(value, str) or not value.strip():
            fail(f"{key} must be a non-empty string")

    if isinstance(ident, str) and ident.strip():
        if not ID_RE.match(ident):
            fail(f"id {ident!r} is not kebab-case (lower-case words joined by '-')")
        if ident in seen_ids:
            fail(f"id {ident!r} is not unique "
                 f"(already used by sources[{seen_ids[ident]}])")
        else:
            seen_ids[ident] = index

    url = entry.get("url")
    if isinstance(url, str) and url.strip():
        if not url.startswith(("http://", "https://")):
            fail(f"url {url!r} does not start with http:// or https://")
        if url in seen_urls:
            fail(f"url {url} is not unique (already used by {seen_urls[url]!r})")
        else:
            seen_urls[url] = locus

    style_guide_url = entry.get("style_guide_url", url)
    if "style_guide_url" in entry and (
        not isinstance(style_guide_url, str) or not style_guide_url.strip()
    ):
        fail("style_guide_url must be a non-empty string when the key is present")
        style_guide_url = None
    if isinstance(style_guide_url, str) and style_guide_url.strip():
        if not style_guide_url.startswith(("http://", "https://")):
            fail(f"style_guide_url {style_guide_url!r} does not start with "
                 "http:// or https://")
        claimed.setdefault(style_guide_url, []).append(locus)
        if section is not None and style_guide_url not in section:
            fail(f"style_guide_url {style_guide_url} does not occur in "
                 f"{GUIDE_LABEL} '{SOURCES_HEADING}': the guide no longer cites "
                 "this source, or the URL changed on one side only")

    if "style_guide_edition" in entry:
        edition = entry.get("style_guide_edition")
        if edition is not None:
            if not isinstance(edition, str) or not edition.strip():
                fail("style_guide_edition must be a non-empty string or null")
            elif section is not None and edition not in section:
                fail(f"style_guide_edition {edition!r} does not occur in "
                     f"{GUIDE_LABEL} '{SOURCES_HEADING}': the edition was bumped "
                     "on one side only")

    if "note" in entry:
        note = entry.get("note")
        if note is not None and (not isinstance(note, str) or not note.strip()):
            fail("note must be a non-empty string or null")

    return out


# --------------------------------------------------------------------------
# the network check


def fetch_status(entry: dict) -> tuple[str, str]:
    """(status, detail) for one entry: one GET, no retries, nothing raised.

    A non-200 response, a request exception and a body without the token are all
    reportable outcomes — never crashes and never silent passes.
    """
    url = entry["url"]
    token = entry["edition_token"]
    try:
        response = requests.get(url, timeout=FETCH_TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        return "ERROR", f"{type(exc).__name__}: {exc}"
    if response.status_code != 200:
        return "ERROR", f"HTTP {response.status_code} from {url}"
    if token not in response.text:
        return "MISSING", (f"token absent from {len(response.content)} bytes "
                           f"fetched from {url}")
    return "OK", f'token found: "{token}"'


# --------------------------------------------------------------------------
# CLI


def report_violations(violations: list[str], manifest_path: Path) -> int:
    for violation in violations:
        print(f"FAIL {violation}")
    print(f"{len(violations)} violation(s) in {manifest_path}")
    return 1


def cmd_verify_manifest(args) -> int:
    manifest_path = Path(args.manifest)
    violations = manifest_violations(manifest_path, STYLE_GUIDE_PATH)
    if violations:
        return report_violations(violations, manifest_path)
    document, _ = _load_manifest(manifest_path)
    print(f"OK: {len(document['sources'])} source(s) consistent with {GUIDE_LABEL}")
    return 0


def cmd_check(args) -> int:
    manifest_path = Path(args.manifest)
    violations = manifest_violations(manifest_path, STYLE_GUIDE_PATH)
    if violations:
        # Never hit the network on a broken manifest: the report would describe
        # sources the guide no longer cites.
        return report_violations(violations, manifest_path)

    document, _ = _load_manifest(manifest_path)
    counts = {"OK": 0, "MISSING": 0, "ERROR": 0}
    for entry in document["sources"]:
        status, detail = fetch_status(entry)
        counts[status] += 1
        print(f"{entry['id']}  {status:<7}  {detail}")
    print(f"sources: {counts['OK']} ok, {counts['MISSING']} missing, "
          f"{counts['ERROR']} error")
    return 0 if counts["MISSING"] == 0 and counts["ERROR"] == 0 else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser(
        "verify-manifest",
        help=f"offline: assert the manifest matches {GUIDE_LABEL} '{SOURCES_HEADING}'",
    )
    verify.add_argument("--manifest", default=str(MANIFEST_PATH),
                        help=f"manifest file (default: {MANIFEST_PATH})")
    verify.set_defaults(func=cmd_verify_manifest)

    check = sub.add_parser(
        "check",
        help="network: fetch every source and report whether its edition token "
             "is still present",
    )
    check.add_argument("--manifest", default=str(MANIFEST_PATH),
                       help=f"manifest file (default: {MANIFEST_PATH})")
    check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
