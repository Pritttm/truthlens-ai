"""
TruthLens AI – Misinformation Detection System
FastAPI Backend Entry Point
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging
import time

from app.rag_pipeline import RagPipeline
from app.claim_extractor import ClaimExtractor
from app.fact_checker import FactChecker

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("truthlens")

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(
    title="TruthLens AI",
    description="Misinformation Detection System powered by LLM + RAG",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Lazy singletons (initialised on first request)
# ──────────────────────────────────────────────
_rag_pipeline: Optional[RagPipeline] = None
_claim_extractor: Optional[ClaimExtractor] = None
_fact_checker: Optional[FactChecker] = None


def get_pipeline() -> tuple[RagPipeline, ClaimExtractor, FactChecker]:
    global _rag_pipeline, _claim_extractor, _fact_checker
    if _rag_pipeline is None:
        logger.info("Initialising AI pipeline components …")
        _rag_pipeline = RagPipeline()
        _claim_extractor = ClaimExtractor()
        _fact_checker = FactChecker(_rag_pipeline)
        logger.info("Pipeline ready.")
    return _rag_pipeline, _claim_extractor, _fact_checker


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    text: str
    url: Optional[str] = None          # optional URL for scraping


class ClaimResult(BaseModel):
    claim: str
    credibility_score: int             # 0–100
    assessment: str


class AnalyzeResponse(BaseModel):
    credibility_score: int             # overall 0–100
    misinformation_probability: str    # Low / Moderate / High / Very High
    explanation: str
    claims: list[ClaimResult]
    sources: list[str]
    processing_time_ms: int


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _probability_label(score: int) -> str:
    if score >= 80:
        return "Low"
    elif score >= 55:
        return "Moderate"
    elif score >= 30:
        return "High"
    return "Very High"


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "TruthLens AI"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Main analysis endpoint.

    Accepts raw text (and optionally a URL to scrape).
    Returns credibility score, per-claim breakdown, and sources.
    """
    t0 = time.perf_counter()

    # ── 0. Input validation ──────────────────────────────────────
    text = request.text.strip()
    if len(text) < 30:
        raise HTTPException(
            status_code=422,
            detail="Input text is too short. Please provide at least one sentence.",
        )
    if len(text) > 15_000:
        raise HTTPException(
            status_code=422,
            detail="Input text exceeds the 15,000 character limit.",
        )

    # ── 1. URL scraping (optional) ───────────────────────────────
    if request.url:
        try:
            from app.scraper import scrape_article
            scraped = scrape_article(request.url)
            if scraped:
                text = scraped
                logger.info("Scraped %d chars from URL: %s", len(text), request.url)
        except Exception as exc:
            logger.warning("Scraping failed (%s); falling back to pasted text.", exc)

    # ── 2. Get pipeline components ───────────────────────────────
    rag, extractor, checker = get_pipeline()

    # ── 3. Extract claims ────────────────────────────────────────
    logger.info("Extracting claims …")
    claims_raw: list[str] = extractor.extract(text)
    if not claims_raw:
        raise HTTPException(
            status_code=422,
            detail="Could not extract any factual claims from the input.",
        )
    logger.info("Extracted %d claims.", len(claims_raw))

    # ── 4. Fact-check each claim via RAG ─────────────────────────
    logger.info("Running RAG fact-checking …")
    claim_results, all_sources = checker.check_claims(claims_raw)

    # ── 5. Aggregate score ───────────────────────────────────────
    overall_score = (
        sum(c.credibility_score for c in claim_results) // len(claim_results)
        if claim_results
        else 50
    )
    prob_label = _probability_label(overall_score)

    # ── 6. Build explanation ─────────────────────────────────────
    explanation = checker.build_explanation(overall_score, claim_results)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "Analysis complete. Score=%d | Probability=%s | Time=%dms",
        overall_score, prob_label, elapsed_ms,
    )

    return AnalyzeResponse(
    credibility_score=overall_score,
    misinformation_probability=prob_label,
    explanation=explanation,
    claims=[
        {"claim": r.claim, "credibility_score": r.credibility_score, "assessment": r.assessment}
        for r in claim_results
    ],
    sources=list(dict.fromkeys(all_sources))[:10],
    processing_time_ms=elapsed_ms,
)
