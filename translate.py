"""
Translation engine: classifies input, calls OpenAI with structured output.
Word → definition + IPA + ZH translation.
Sentence/paragraph → ZH translation.
"""
import json
import logging
import re

from openai import OpenAI
import cache as _cache
import settings as _settings

log = logging.getLogger(__name__)


class TranslationError(Exception):
    pass


_WORD_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "word_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "word":           {"type": "string"},
                "ipa":            {"type": "string"},
                "part_of_speech": {"type": "string"},
                "en_definition":  {"type": "string"},
                "zh_translation": {"type": "string"},
                "example":        {"type": "string"},
            },
            "required": ["word", "ipa", "part_of_speech", "en_definition", "zh_translation", "example"],
            "additionalProperties": False,
        },
    },
}

_SENTENCE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sentence_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "zh_translation": {"type": "string"},
                "note":           {"type": "string"},
            },
            "required": ["zh_translation", "note"],
            "additionalProperties": False,
        },
    },
}

# Singleton client — created once, reused across calls
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    api_key = _settings.get("api_key", "")
    if _client is None:
        _client = OpenAI(api_key=api_key)
    return _client


def _invalidate_client():
    """Call when the API key changes."""
    global _client
    _client = None


def _parse_response(response, required_fields: list[str]) -> dict:
    """Validate an OpenAI structured-output response and return the parsed dict."""
    choices = getattr(response, "choices", None)
    if not choices:
        raise TranslationError("OpenAI returned no choices")

    msg = choices[0].message
    refusal = getattr(msg, "refusal", None)
    if refusal:
        raise TranslationError(f"OpenAI refused the request: {refusal}")

    content = getattr(msg, "content", None)
    if not content:
        raise TranslationError("OpenAI returned an empty response")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise TranslationError(f"OpenAI response is not valid JSON: {e}") from e

    missing = [f for f in required_fields if f not in data]
    if missing:
        raise TranslationError(f"OpenAI response missing fields: {missing}")

    return data


def classify(text: str) -> str:
    stripped = text.strip()
    if re.match(r"^[A-Za-z'-]+$", stripped):
        return "word"
    return "sentence"


def translate(text: str, context: str = "") -> dict:
    mode = classify(text)
    cached = _cache.lookup(text, mode)
    if cached:
        return cached

    client = _get_client()

    if mode == "word":
        result = _word_lookup(client, text, context)
    else:
        result = _sentence_translate(client, text)

    result["mode"] = mode
    _cache.store(text, mode, result)
    return result


def _word_lookup(client: OpenAI, word: str, context: str) -> dict:
    ctx_note = f'\nContext sentence: "{context}"' if context else ""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format=_WORD_SCHEMA,
            max_tokens=300,
            timeout=12,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an English dictionary for Chinese learners. "
                        "Return the word's IPA, part of speech, English definition, "
                        "Chinese translation, and one example sentence."
                        + ctx_note
                    ),
                },
                {"role": "user", "content": word},
            ],
        )
    except Exception as e:
        raise TranslationError(str(e)) from e

    return _parse_response(response, ["word", "ipa", "part_of_speech", "en_definition", "zh_translation", "example"])


def _sentence_translate(client: OpenAI, text: str) -> dict:
    truncated = text[:1500]
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format=_SENTENCE_SCHEMA,
            max_tokens=500,
            timeout=20,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the English text to Chinese. "
                        "If there is a subtle point worth noting (idiom, cultural reference, ambiguity), "
                        "add a brief note in Chinese. Otherwise leave note empty."
                    ),
                },
                {"role": "user", "content": truncated},
            ],
        )
    except Exception as e:
        raise TranslationError(str(e)) from e

    return _parse_response(response, ["zh_translation", "note"])
