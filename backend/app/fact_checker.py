"""
TruthLens AI – Fact Checker
Uses an LLM (or heuristic fallback) to score each claim against
the documents retrieved by the RAG pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from app.rag_pipeline import RagPipeline, RetrievedDoc

logger = logging.getLogger("truthlens.fact_checker")

# ─────────────────────────────────────────────────────────────────
# Prompt templates
# ─────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are TruthLens, an expert misinformation analyst.

Your job:
1. Read the CLAIM provided by the user.
2. Read the RETRIEVED SOURCES that may or may not support the claim.
3. Evaluate the credibility of the claim based on the sources.

Output ONLY a valid JSON object with these keys:
  credibility_score : integer 0–100
      (100 = fully verified, 0 = clear disinformation)
  assessment        : one of "Verified", "Likely True", "Unverifiable",
                      "Misleading", "Likely False", "False"
  reasoning         : 1–3 sentences explaining the score

Do not add any text outside the JSON object."""

_USER_PROMPT = """CLAIM:
{claim}

RETRIEVED SOURCES:
{sources_block}

Evaluate the claim's credibility."""


class ClaimResult:
    """Mirrors the Pydantic schema in main.py – kept as plain class for reuse."""

    def __init__(self, claim: str, credibility_score: int, assessment: str):
        self.claim = claim
        self.credibility_score = credibility_score
        self.assessment = assessment

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "credibility_score": self.credibility_score,
            "assessment": self.assessment,
        }


class FactChecker:
    """
    Coordinates RAG retrieval + LLM scoring for each extracted claim.
    """

    def __init__(
        self,
        rag_pipeline: RagPipeline,
        model: str = "gpt-4o-mini",
        max_tokens: int = 300,
    ):
        self._rag = rag_pipeline
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
                from openai import OpenAI   # type: ignore
                self._client = OpenAI(api_key=api_key)
                logger.info("FactChecker: OpenAI client initialised.")
            except ImportError:
                logger.warning("openai not installed; heuristic scoring will be used.")
        else:
            logger.warning("OPENAI_API_KEY not set; heuristic scoring will be used.")

    # ──────────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────────
    def check_claims(
        self, claims: list[str]
    ) -> tuple[list[ClaimResult], list[str]]:
        """
        For each claim:
          1. Retrieve top-k relevant docs via RAG.
          2. Score the claim with the LLM (or heuristic).
        Returns (list of ClaimResult, flat list of source URLs).
        """
        results: list[ClaimResult] = []
        all_sources: list[str] = []

        for claim in claims:
            docs = self._rag.retrieve(claim)
            all_sources.extend(d.source for d in docs)

            if self._client:
                result = self._llm_score(claim, docs)
            else:
                result = self._heuristic_score(claim, docs)

            results.append(result)

        return results, all_sources

    # ──────────────────────────────────────────────────────────────
    # LLM scoring
    # ──────────────────────────────────────────────────────────────
    def _llm_score(self, claim: str, docs: list[RetrievedDoc]) -> ClaimResult:
        sources_block = "\n".join(
            f"[{i+1}] ({d.source})\n{d.content[:400]}"
            for i, d in enumerate(docs)
        ) or "No relevant sources retrieved."

        user_msg = _USER_PROMPT.format(claim=claim, sources_block=sources_block)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=self._max_tokens,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            return self._parse_llm_result(claim, raw)
        except Exception as exc:
            logger.error("LLM scoring failed for claim '%s': %s", claim[:60], exc)
            return self._heuristic_score(claim, docs)

    def _parse_llm_result(self, claim: str, raw: str) -> ClaimResult:
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        try:
            data = json.loads(raw)
            score = max(0, min(100, int(data.get("credibility_score", 50))))
            assessment = str(data.get("assessment", "Unverifiable"))
            return ClaimResult(claim=claim, credibility_score=score, assessment=assessment)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Could not parse LLM JSON (%s); raw=%s", exc, raw[:120])
            return ClaimResult(claim=claim, credibility_score=50, assessment="Unverifiable")

    # ──────────────────────────────────────────────────────────────
    # Heuristic fallback
    # ──────────────────────────────────────────────────────────────
    def _heuristic_score(self, claim: str, docs: list[RetrievedDoc]) -> ClaimResult:
        """
        Simple keyword-overlap heuristic when the LLM is unavailable.
        Maps average document relevance to a credibility score.
        """
        if not docs:
            return ClaimResult(
                claim=claim, credibility_score=40, assessment="Unverifiable"
            )

        # Weighted average relevance from retrieved docs
        avg_rel = sum(d.relevance for d in docs) / len(docs)
        score = int(50 + avg_rel * 40)          # maps [0,1] → [50,90]
        score = max(30, min(90, score))

        # Crude keyword check for obvious false-flag phrases
        false_signals = [
            "conspiracy", "hoax", "fake", "fraud", "lie", "false flag",
            "they don't want you to know", "secret cure", "plandemic",
        ]
        claim_lower = claim.lower()
        hits = sum(1 for s in false_signals if s in claim_lower)
        score -= hits * 10
        score = max(10, min(90, score))

        assessment = (
            "Likely True" if score >= 70
            else "Unverifiable" if score >= 50
            else "Misleading" if score >= 30
            else "Likely False"
        )
        return ClaimResult(claim=claim, credibility_score=score, assessment=assessment)

    # ──────────────────────────────────────────────────────────────
    # Explanation synthesis
    # ──────────────────────────────────────────────────────────────
    def build_explanation(
        self, overall_score: int, results: list[ClaimResult]
    ) -> str:
        """Build a human-readable summary from all claim results."""
        verified = [r for r in results if r.credibility_score >= 70]
        disputed = [r for r in results if r.credibility_score < 50]

        lines: list[str] = []

        if overall_score >= 80:
            lines.append(
                f"The content appears credible (overall score: {overall_score}/100). "
                "The main claims are supported by reliable sources."
            )
        elif overall_score >= 55:
            lines.append(
                f"The content has mixed credibility (score: {overall_score}/100). "
                "Some claims are well-supported, but others require further verification."
            )
        elif overall_score >= 30:
            lines.append(
                f"The content contains potentially misleading information "
                f"(score: {overall_score}/100). Several claims contradict trusted sources."
            )
        else:
            lines.append(
                f"The content shows strong indicators of misinformation "
                f"(score: {overall_score}/100). Most claims are not supported by "
                "credible evidence."
            )

        if verified:
            v_claims = "; ".join(r.claim[:80] for r in verified[:2])
            lines.append(f"Verified claims include: {v_claims}.")

        if disputed:
            d_claims = "; ".join(r.claim[:80] for r in disputed[:2])
            lines.append(f"Disputed or unverifiable claims: {d_claims}.")

        return " ".join(lines)
