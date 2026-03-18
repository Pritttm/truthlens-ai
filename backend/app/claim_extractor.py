"""
TruthLens AI – Claim Extractor
Pulls distinct, verifiable factual claims from arbitrary text using an LLM.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("truthlens.claim_extractor")

# ─────────────────────────────────────────────────────────────────
# Prompt template
# ─────────────────────────────────────────────────────────────────
_EXTRACTION_SYSTEM = """You are a fact-checking assistant.
Your task: read the provided text and extract the key FACTUAL claims that can be
independently verified.

Rules:
- Return ONLY a JSON array of strings (the claims).
- Each claim must be a single, self-contained sentence.
- Omit opinions, predictions, and rhetorical questions.
- Omit trivial or obvious statements.
- Extract between 1 and 8 claims.
- Do not add any commentary outside the JSON array.

Example output:
["The Eiffel Tower is 330 metres tall.",
 "It was built in 1889 for the World Fair.",
 "France is the most visited country in the world."]
"""

_EXTRACTION_USER = """Text:
\"\"\"
{text}
\"\"\"

Extract the key factual claims as a JSON array."""


class ClaimExtractor:
    """
    Uses the configured LLM to extract verifiable factual claims from text.

    Falls back to a simple heuristic splitter when the API is unavailable
    (useful for local dev without an API key).
    """

    def __init__(self, model: str = "gpt-4o-mini", max_tokens: int = 512):
        self._model = model
        self._max_tokens = max_tokens
        self._client: Optional[object] = None
        self._init_client()

    # ──────────────────────────────────────────────────────────────
    # Initialisation
    # ──────────────────────────────────────────────────────────────
    def _init_client(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            try:
                from openai import OpenAI  # type: ignore
                self._client = OpenAI(api_key=api_key)
                logger.info("ClaimExtractor: OpenAI client initialised.")
            except ImportError:
                logger.warning("openai package not installed; using heuristic fallback.")
        else:
            logger.warning("OPENAI_API_KEY not set; using heuristic claim extractor.")

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    def extract(self, text: str) -> list[str]:
        """Return a list of factual claim strings extracted from *text*."""
        if self._client:
            try:
                return self._llm_extract(text)
            except Exception as exc:
                logger.error("LLM extraction failed (%s); falling back.", exc)
        return self._heuristic_extract(text)

    # ──────────────────────────────────────────────────────────────
    # LLM path
    # ──────────────────────────────────────────────────────────────
    def _llm_extract(self, text: str) -> list[str]:
        # Truncate very long inputs to avoid token overruns
        text_trimmed = text[:6000]

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM},
                {
                    "role": "user",
                    "content": _EXTRACTION_USER.format(text=text_trimmed),
                },
            ],
            max_tokens=self._max_tokens,
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()
        claims = self._parse_json_claims(raw)
        logger.info("LLM extracted %d claims.", len(claims))
        return claims

    # ──────────────────────────────────────────────────────────────
    # Heuristic fallback
    # ──────────────────────────────────────────────────────────────
    def _heuristic_extract(self, text: str) -> list[str]:
        """
        Naive sentence splitter that picks sentences likely to contain
        verifiable facts (numbers, proper nouns, dates, etc.).
        """
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)
        factual: list[str] = []
        fact_pattern = re.compile(
            r"\b(\d{4}|\d+%|[A-Z][a-z]+ [A-Z][a-z]+|million|billion|trillion"
            r"|percent|according to|study|report|said|announced|confirmed)\b"
        )
        for s in sentences:
            s = s.strip()
            if 20 < len(s) < 300 and fact_pattern.search(s):
                factual.append(s)
            if len(factual) >= 8:
                break

        if not factual:
            # Last resort: first 5 sentences
            factual = [s.strip() for s in sentences[:5] if len(s.strip()) > 20]

        logger.info("Heuristic extracted %d claims.", len(factual))
        return factual

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_json_claims(raw: str) -> list[str]:
        """Robustly parse a JSON array from LLM output."""
        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(c) for c in parsed if isinstance(c, str) and c.strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: extract quoted strings
        fallback = re.findall(r'"([^"]{10,})"', raw)
        return fallback or [raw] if raw else []
