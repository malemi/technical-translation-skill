#!/usr/bin/env python3
"""Translate a project's abstract+description to English via the DeepL document API.

Usage: translate_deepl.py run --project projects/<slug> [--target EN-US]

Builds work/description_it.docx (a copy of source.docx minus the title
paragraphs and the whole claims section), uploads it to DeepL with the project
glossary, polls until done, downloads work/description_en.docx and writes or
merges state/translations.json, pairing every remaining non-empty paragraph
with its segment id. Requires a paid DEEPL_AUTH_KEY and a pushed glossary
(state/deepl.json from glossary.py push).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time

import requests

import common

SENT_SECTIONS = ("abstract", "description")
REMOVED_SECTIONS = ("title", "claims")
RETRY_DELAYS_S = (1, 4, 9)
POLL_TIMEOUT_S = 900
POLL_MAX_INTERVAL_S = 5
POLL_REQUEST_TIMEOUT_S = 30
TRANSFER_TIMEOUT_S = 300
DOCX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document")
INVALIDATION_REASON = "deepl re-run invalidated final"


# --------------------------------------------------------------------------
# HTTP with the contract retry policy


def _deepl_post(url, *, key, data=None, files=None, timeout, what):
    """POST to DeepL. 429/5xx (and transport errors) are retried 3 times with
    1/4/9 s backoff; any other 4xx fails immediately with the response body."""
    headers = {"Authorization": f"DeepL-Auth-Key {key}"}
    attempts = len(RETRY_DELAYS_S) + 1
    last_failure = None
    for attempt in range(attempts):
        if attempt:
            delay = RETRY_DELAYS_S[attempt - 1]
            print(
                f"WARNING: {what} failed ({last_failure}); "
                f"retry {attempt}/{len(RETRY_DELAYS_S)} in {delay} s",
                file=sys.stderr,
            )
            time.sleep(delay)
        try:
            response = requests.post(
                url, data=data, files=files, headers=headers, timeout=timeout
            )
        except requests.RequestException as exc:
            last_failure = str(exc)
            continue
        if response.status_code == 456:
            common.die("DeepL monthly character quota exceeded (HTTP 456)")
        if response.status_code == 429 or response.status_code >= 500:
            last_failure = f"HTTP {response.status_code}: {response.text[:200]}"
            continue
        if response.status_code >= 400:
            common.die(
                f"{what} failed: HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )
        return response
    common.die(f"{what} failed after {attempts} attempts: {last_failure}")


def _json_or_die(response, what):
    try:
        return response.json()
    except ValueError:
        common.die(f"{what}: non-JSON response: {response.text[:500]}")


# --------------------------------------------------------------------------
# step 1: build the document to send


def build_description_docx(paths, segments_doc) -> list[str]:
    """Copy source.docx to work/description_it.docx, delete the title
    paragraphs and the whole claims section (heading included), keep everything
    else (empty paragraphs stay). Returns the segment ids of the remaining
    non-empty paragraphs (abstract + headings + description), in order."""
    from docx import Document

    segments = segments_doc["segments"]
    paths["work"].mkdir(parents=True, exist_ok=True)
    work_docx = paths["work"] / "description_it.docx"
    shutil.copyfile(paths["source"], work_docx)

    document = Document(str(work_docx))
    paragraphs = list(document.paragraphs)
    to_remove = []
    for segment in segments:
        parts = segment["parts_it"] or [segment["text_it"]]
        if len(parts) != len(segment["docx_indices"]):
            common.die(
                f"segment {segment['id']}: parts_it/docx_indices length "
                "mismatch in segments.json"
            )
        for part, index in zip(parts, segment["docx_indices"]):
            if index >= len(paragraphs):
                common.die(
                    f"segment {segment['id']}: docx index {index} out of "
                    "range; source.docx changed since ingest — re-run ingest.py"
                )
            if paragraphs[index].text != part:
                common.die(
                    f"segment {segment['id']}: paragraph {index} text differs "
                    "from segments.json; source.docx changed since ingest — "
                    "re-run ingest.py"
                )
            if segment["section"] in REMOVED_SECTIONS:
                to_remove.append(paragraphs[index])
    for paragraph in to_remove:
        # python-docx has no public paragraph delete; removing the underlying
        # XML element is the standard idiom.
        paragraph._element.getparent().remove(paragraph._element)
    document.save(str(work_docx))

    sent_ids = [s["id"] for s in segments if s["section"] in SENT_SECTIONS]
    remaining = [
        text for _, text, _ in common.iter_body_paragraphs(work_docx)
        if common.normalize(text)
    ]
    if len(remaining) != len(sent_ids):
        common.die(
            f"internal error: {len(remaining)} non-empty paragraphs remain in "
            f"{work_docx.name} but {len(sent_ids)} segment ids were recorded"
        )
    return sent_ids


# --------------------------------------------------------------------------
# steps 2: DeepL document API


def build_document_params(target_lang: str, glossary_id: str) -> dict:
    return {
        "source_lang": "IT",
        "target_lang": target_lang,
        "glossary_id": glossary_id,
    }


def upload_document(api_base, key, docx_path, target_lang, glossary_id):
    # Bytes, not a file handle: the payload must be re-sendable on retry.
    files = {"file": (docx_path.name, docx_path.read_bytes(), DOCX_MIME)}
    response = _deepl_post(
        f"{api_base}/v2/document", key=key,
        data=build_document_params(target_lang, glossary_id),
        files=files, timeout=TRANSFER_TIMEOUT_S, what="document upload",
    )
    payload = _json_or_die(response, "document upload")
    document_id = payload.get("document_id")
    document_key = payload.get("document_key")
    if not document_id or not document_key:
        common.die(
            f"document upload: missing document_id/document_key in response: "
            f"{payload}"
        )
    return document_id, document_key


def poll_document(api_base, key, document_id, document_key) -> int:
    """Poll until status=done; returns billed_characters."""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while True:
        response = _deepl_post(
            f"{api_base}/v2/document/{document_id}", key=key,
            data={"document_key": document_key},
            timeout=POLL_REQUEST_TIMEOUT_S, what="document status poll",
        )
        payload = _json_or_die(response, "document status poll")
        status = payload.get("status")
        if status == "done":
            billed = payload.get("billed_characters")
            if not isinstance(billed, int):
                common.die(
                    f"document status done but no billed_characters: {payload}"
                )
            return billed
        if status == "error":
            message = (payload.get("message")
                       or payload.get("error_message") or str(payload))
            common.die(f"DeepL document translation failed: {message}")
        if status not in ("queued", "translating"):
            common.die(f"document status: unexpected status {status!r}: {payload}")
        if time.monotonic() >= deadline:
            common.die(
                f"document translation not done after "
                f"{POLL_TIMEOUT_S // 60} minutes; giving up"
            )
        interval = POLL_MAX_INTERVAL_S
        hint = payload.get("seconds_remaining")
        if isinstance(hint, int) and 0 < hint < POLL_MAX_INTERVAL_S:
            interval = hint
        time.sleep(interval)


def download_document(api_base, key, document_id, document_key, out_path):
    response = _deepl_post(
        f"{api_base}/v2/document/{document_id}/result", key=key,
        data={"document_key": document_key},
        timeout=TRANSFER_TIMEOUT_S, what="document download",
    )
    out_path.write_bytes(response.content)


# --------------------------------------------------------------------------
# step 3: pairing and merge with invalidation rules


def merge_translations(existing, sent_ids, en_texts, target_lang):
    """Build the new translations.json content. A pair whose DeepL text
    changed loses its final (edit appended); an unchanged pair is kept as-is;
    pairs for ids no longer sent are dropped. Returns (doc, stats)."""
    old_pairs = {}
    title = {"text_en": None}
    if existing is not None:
        old_pairs = {pair["id"]: pair for pair in existing["pairs"]}
        title = existing["title"]
    stats = {"new": 0, "unchanged": 0, "updated": 0, "invalidated": 0,
             "dropped": 0}
    pairs = []
    for segment_id, text_en in zip(sent_ids, en_texts):
        old = old_pairs.pop(segment_id, None)
        if old is not None and old["text_en_deepl"] == text_en:
            pairs.append(old)
            stats["unchanged"] += 1
            continue
        pair = {
            "id": segment_id,
            "text_en_deepl": text_en,
            "deepl_para_sha256": common.sha256_text(text_en),
            "text_en_final": None,
            "edits": [],
        }
        if old is None:
            stats["new"] += 1
        else:
            stats["updated"] += 1
            if old["text_en_final"] is not None:
                stats["invalidated"] += 1
            pair["edits"] = old["edits"] + [{
                "reason": INVALIDATION_REASON,
                "old_final": old["text_en_final"],
                "at": common.now_iso(),
            }]
        pairs.append(pair)
    stats["dropped"] = len(old_pairs)
    return {"target_lang": target_lang, "title": title, "pairs": pairs}, stats


# --------------------------------------------------------------------------
# CLI


def cmd_run(args) -> int:
    paths = common.project_paths(args.project)
    key, api_base = common.load_env_key()

    violations = common.validate_file(paths["segments"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("invalid segments.json — re-run ingest.py")
    segments_doc = common.read_json(paths["segments"])

    if not paths["deepl"].is_file():
        common.die("state/deepl.json not found — run glossary.py push first")
    deepl_state = common.read_json(paths["deepl"])
    glossary_id = deepl_state.get("glossary_id")
    if not glossary_id:
        common.die(
            "state/deepl.json has no glossary_id — run glossary.py push first"
        )
    # The authoritative endpoint is derived from the key suffix; if deepl.json
    # stored a different base (e.g. glossary pushed with another key), trust the
    # key-derived one.
    stored_base = deepl_state.get("api_base")
    if stored_base and stored_base != api_base:
        print(
            f"WARNING: state/deepl.json api_base {stored_base!r} disagrees with "
            f"key-derived {api_base!r}; using the key-derived base",
            file=sys.stderr,
        )

    sent_ids = build_description_docx(paths, segments_doc)
    work_it = paths["work"] / "description_it.docx"
    print(f"Built {work_it} ({len(sent_ids)} segments to translate)")

    document_id, document_key = upload_document(
        api_base, key, work_it, args.target, glossary_id
    )
    print(f"Uploaded (document_id {document_id}); polling until done...")
    billed = poll_document(api_base, key, document_id, document_key)
    en_path = paths["work"] / "description_en.docx"
    download_document(api_base, key, document_id, document_key, en_path)

    # Billing happened regardless of what pairing finds: record it now.
    deepl_state["document"] = {
        "billed_characters": billed,
        "translated_at": common.now_iso(),
    }
    common.write_json(paths["deepl"], deepl_state)

    en_texts = [
        text for _, text, _ in common.iter_body_paragraphs(en_path)
        if common.normalize(text)
    ]
    if len(en_texts) != len(sent_ids):
        print(
            f"ERROR: paragraph count mismatch: sent {len(sent_ids)} segments, "
            f"received {len(en_texts)} non-empty paragraphs in {en_path.name}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    existing = None
    if paths["translations"].is_file():
        violations = common.validate_file(paths["translations"])
        if violations:
            for violation in violations:
                print(f"FAIL {violation}", file=sys.stderr)
            common.die("existing translations.json is invalid — fix or remove it")
        existing = common.read_json(paths["translations"])
    doc, stats = merge_translations(existing, sent_ids, en_texts, args.target)
    common.write_json(paths["translations"], doc)
    violations = common.validate_file(paths["translations"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("run produced an invalid translations.json (bug)")

    print(f"billed_characters: {billed}")
    print(
        f"Translated {len(sent_ids)} segments to {args.target}; "
        f"EN document: {en_path}"
    )
    print(
        f"Pairs: {stats['new']} new, {stats['unchanged']} unchanged, "
        f"{stats['updated']} updated ({stats['invalidated']} finals "
        f"invalidated), {stats['dropped']} dropped"
    )
    print(f"State updated: {paths['translations']} and {paths['deepl']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument(
        "--project", required=True,
        help="project directory, e.g. projects/_fixture",
    )
    run_parser.add_argument(
        "--target", default="EN-US",
        help="DeepL target language (default: EN-US)",
    )
    args = parser.parse_args()
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
