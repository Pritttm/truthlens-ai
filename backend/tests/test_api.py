"""
TruthLens AI – API Integration Tests
Run with: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# We patch heavy dependencies before importing the app
@pytest.fixture(scope="session", autouse=True)
def patch_pipeline():
    """Prevent real LLM / ChromaDB calls during tests."""
    with patch("app.rag_pipeline.RagPipeline._init_chroma"), \
         patch("app.rag_pipeline.RagPipeline._seed_corpus"), \
         patch("app.embeddings.EmbeddingEngine._load"):
        yield


@pytest.fixture(scope="session")
def client():
    from app.main import app
    return TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Input validation ──────────────────────────────────────────────────────────
def test_analyze_empty_text(client):
    r = client.post("/analyze", json={"text": ""})
    assert r.status_code == 422


def test_analyze_too_short(client):
    r = client.post("/analyze", json={"text": "short"})
    assert r.status_code == 422


def test_analyze_too_long(client):
    r = client.post("/analyze", json={"text": "a" * 16_000})
    assert r.status_code == 422


# ── Happy path (with mocked pipeline) ────────────────────────────────────────
def _mock_claim_result():
    from app.fact_checker import ClaimResult
    return ClaimResult(
        claim="The sky is blue.",
        credibility_score=85,
        assessment="Verified",
    )


def test_analyze_success(client):
    sample_text = (
        "Scientists at NASA confirmed last week that the James Webb Space Telescope "
        "has discovered water vapour in the atmosphere of an exoplanet 700 light-years "
        "away. The finding was published in Nature and announced at a press conference."
    )

    mock_result = [_mock_claim_result()]
    mock_sources = ["https://en.wikipedia.org/wiki/James_Webb_Space_Telescope"]

    with patch("app.main.get_pipeline") as mock_get, \
         patch("app.claim_extractor.ClaimExtractor.extract", return_value=["Test claim."]), \
         patch("app.fact_checker.FactChecker.check_claims", return_value=(mock_result, mock_sources)), \
         patch("app.fact_checker.FactChecker.build_explanation", return_value="Content appears credible."):

        mock_rag = MagicMock()
        mock_extractor = MagicMock()
        mock_checker = MagicMock()
        mock_extractor.extract.return_value = ["Test claim."]
        mock_checker.check_claims.return_value = (mock_result, mock_sources)
        mock_checker.build_explanation.return_value = "Content appears credible."
        mock_get.return_value = (mock_rag, mock_extractor, mock_checker)

        r = client.post("/analyze", json={"text": sample_text})

    assert r.status_code == 200
    data = r.json()
    assert "credibility_score" in data
    assert "misinformation_probability" in data
    assert "explanation" in data
    assert "claims" in data
    assert "sources" in data
    assert isinstance(data["credibility_score"], int)
    assert 0 <= data["credibility_score"] <= 100


# ── Claim extractor unit tests ────────────────────────────────────────────────
def test_heuristic_extractor():
    from app.claim_extractor import ClaimExtractor
    extractor = ClaimExtractor.__new__(ClaimExtractor)
    extractor._client = None

    text = (
        "According to a 2023 report by the WHO, over 1 billion people lack "
        "access to clean water. The United Nations confirmed this figure. "
        "Experts say the situation is worsening due to climate change."
    )
    claims = extractor._heuristic_extract(text)
    assert len(claims) >= 1
    assert all(isinstance(c, str) for c in claims)


def test_parse_json_claims_valid():
    from app.claim_extractor import ClaimExtractor
    raw = '["Claim one.", "Claim two.", "Claim three."]'
    result = ClaimExtractor._parse_json_claims(raw)
    assert result == ["Claim one.", "Claim two.", "Claim three."]


def test_parse_json_claims_with_fences():
    from app.claim_extractor import ClaimExtractor
    raw = '```json\n["Claim A.", "Claim B."]\n```'
    result = ClaimExtractor._parse_json_claims(raw)
    assert "Claim A." in result


# ── Fact checker heuristic ────────────────────────────────────────────────────
def test_heuristic_score_no_docs():
    from app.fact_checker import FactChecker
    checker = FactChecker.__new__(FactChecker)
    checker._client = None

    result = checker._heuristic_score("The earth is flat.", [])
    assert result.credibility_score == 40
    assert result.assessment == "Unverifiable"


def test_heuristic_score_false_signal():
    from app.fact_checker import FactChecker
    from app.rag_pipeline import RetrievedDoc

    checker = FactChecker.__new__(FactChecker)
    checker._client = None

    docs = [RetrievedDoc(content="Some content", source="wiki", relevance=0.7)]
    result = checker._heuristic_score("This is a hoax conspiracy they don't want you to know.", docs)
    # Should be penalised
    assert result.credibility_score < 65


# ── Probability label helper ──────────────────────────────────────────────────
def test_probability_labels():
    from app.main import _probability_label
    assert _probability_label(90) == "Low"
    assert _probability_label(60) == "Moderate"
    assert _probability_label(40) == "High"
    assert _probability_label(20) == "Very High"
