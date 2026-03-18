#!/usr/bin/env bash
# TruthLens AI – Quick API smoke test
# Usage: bash scripts/test_api_curl.sh [BASE_URL]

BASE_URL="${1:-http://localhost:8000}"

echo "=== TruthLens AI – API Smoke Test ==="
echo "Target: $BASE_URL"
echo ""

# ── Health check ──────────────────────────────────────────────
echo "1. GET /health"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

# ── Analyze – credible text ───────────────────────────────────
echo "2. POST /analyze – (credible article)"
curl -s -X POST "$BASE_URL/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Scientists at CERN announced last Tuesday that they have successfully measured the mass of the W boson with unprecedented precision. The measurement, published in Science, slightly deviates from Standard Model predictions, potentially hinting at new physics. The experiment involved billions of collision events recorded over several years."
  }' | python3 -m json.tool
echo ""

# ── Analyze – suspicious text ─────────────────────────────────
echo "3. POST /analyze – (suspicious / conspiratorial)"
curl -s -X POST "$BASE_URL/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "5G towers are secretly spreading COVID-19 by beaming virus particles through radio frequencies. This hoax was confirmed by a secret WHO memo leaked online. Governments are hiding the truth and covering up the conspiracy with fake vaccines that contain microchips for population tracking."
  }' | python3 -m json.tool
echo ""

echo "=== Tests complete ==="
