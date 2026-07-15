#!/usr/bin/env python3
"""Back-translate the model-authored English claims to Italian via DeepL.

Usage: backtranslate.py run --project projects/<slug>

Reads state/claims_en.json, translates every claim's text_en EN->IT with the
DeepL text API and writes state/backtranslation.json. Deliberately NO glossary
on this pass: the back-translation must stay a naive, independent probe of the
English claims. Requires a DEEPL_AUTH_KEY (Free or Pro; the endpoint follows
the key suffix).
"""

from __future__ import annotations

import argparse
import sys

import requests

import common

TEXTS_PER_REQUEST = 50  # DeepL /v2/translate limit per request
REQUEST_TIMEOUT_S = 120


def build_translate_params(texts) -> dict:
    """Form parameters for POST /v2/translate ("1" encodes true). No
    glossary_id, by contract: the back pass stays a naive independent probe."""
    return {
        "text": list(texts),
        "source_lang": "EN",
        "target_lang": "IT",
        "split_sentences": "0",
        "preserve_formatting": "1",
    }


def translate_texts(api_base, key, texts) -> list[str]:
    out: list[str] = []
    headers = {"Authorization": f"DeepL-Auth-Key {key}"}
    for start in range(0, len(texts), TEXTS_PER_REQUEST):
        chunk = texts[start:start + TEXTS_PER_REQUEST]
        try:
            response = requests.post(
                f"{api_base}/v2/translate",
                data=build_translate_params(chunk),
                headers=headers,
                timeout=REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            common.die(f"DeepL translate request failed: {exc}")
        if response.status_code == 456:
            common.die("DeepL monthly character quota exceeded (HTTP 456)")
        if response.status_code >= 400:
            common.die(
                f"DeepL translate failed: HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )
        try:
            payload = response.json()
        except ValueError:
            common.die(
                f"DeepL translate: non-JSON response: {response.text[:500]}"
            )
        translations = payload.get("translations")
        if not isinstance(translations, list) or len(translations) != len(chunk):
            got = len(translations) if isinstance(translations, list) else "none"
            common.die(
                f"DeepL translate: expected {len(chunk)} translations, got {got}"
            )
        for item in translations:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                common.die(f"DeepL translate: malformed translation item: {item}")
            out.append(item["text"])
    return out


def cmd_run(args) -> int:
    paths = common.project_paths(args.project, need_source=False)
    key, api_base = common.load_env_key()

    if not paths["claims_en"].is_file():
        common.die(
            "state/claims_en.json not found — the English claims must be "
            "authored before back-translation"
        )
    violations = common.validate_file(paths["claims_en"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("invalid claims_en.json — fix it before back-translation")
    claims = common.read_json(paths["claims_en"])["claims"]
    if not claims:
        common.die("claims_en.json contains no claims")
    for claim in claims:
        if not common.normalize(claim["text_en"]):
            common.die(f"claim {claim['id']}: empty text_en")

    # The authoritative endpoint is derived from the key suffix; if deepl.json
    # stored a different base, trust the key-derived one.
    if paths["deepl"].is_file():
        stored_base = common.read_json(paths["deepl"]).get("api_base")
        if stored_base and stored_base != api_base:
            print(
                f"WARNING: state/deepl.json api_base {stored_base!r} disagrees "
                f"with key-derived {api_base!r}; using the key-derived base",
                file=sys.stderr,
            )

    texts = [claim["text_en"] for claim in claims]
    back_texts = translate_texts(api_base, key, texts)

    data = {
        "claims": [
            {"id": claim["id"], "text_it_back": text}
            for claim, text in zip(claims, back_texts)
        ],
        "run_at": common.now_iso(),
    }
    common.write_json(paths["backtranslation"], data)
    violations = common.validate_file(paths["backtranslation"])
    if violations:
        for violation in violations:
            print(f"FAIL {violation}", file=sys.stderr)
        common.die("run produced an invalid backtranslation.json (bug)")

    print(
        f"Back-translated {len(claims)} claims EN->IT via "
        f"{api_base}/v2/translate (naive: no glossary)"
    )
    print(f"Wrote {paths['backtranslation']}")
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
    args = parser.parse_args()
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
