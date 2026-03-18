import { useState, useRef } from "react";

// ─── API ───────────────────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function analyzeText(text, url) {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, url: url || undefined }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

// ─── Credibility Meter ─────────────────────────────────────────────────────────
function CredibilityMeter({ score }) {
  const clamped = Math.max(0, Math.min(100, score));
  const angle = (clamped / 100) * 180;              // 0° = left, 180° = right

  const getColor = (s) => {
    if (s >= 75) return "#22c55e";
    if (s >= 50) return "#eab308";
    if (s >= 25) return "#f97316";
    return "#ef4444";
  };

  const getLabel = (s) => {
    if (s >= 75) return "Credible";
    if (s >= 50) return "Mixed";
    if (s >= 25) return "Suspicious";
    return "Likely False";
  };

  const color = getColor(clamped);

  // SVG arc path helper
  const polarToXY = (deg, r, cx, cy) => {
    const rad = ((deg - 180) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const arcPath = (startDeg, endDeg, r, cx, cy) => {
    const s = polarToXY(startDeg, r, cx, cy);
    const e = polarToXY(endDeg, r, cx, cy);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  };

  const needleEnd = polarToXY(angle, 68, 100, 100);

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 200 110" className="w-52">
        {/* Track arcs */}
        {[
          { start: 0, end: 45, color: "#ef4444" },
          { start: 45, end: 90, color: "#f97316" },
          { start: 90, end: 135, color: "#eab308" },
          { start: 135, end: 180, color: "#22c55e" },
        ].map((seg, i) => (
          <path
            key={i}
            d={arcPath(seg.start, seg.end, 80, 100, 100)}
            fill="none"
            stroke={seg.color}
            strokeWidth="14"
            strokeLinecap="round"
            opacity="0.25"
          />
        ))}

        {/* Filled progress arc */}
        {clamped > 0 && (
          <path
            d={arcPath(0, angle, 80, 100, 100)}
            fill="none"
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
          />
        )}

        {/* Needle */}
        <line
          x1="100" y1="100"
          x2={needleEnd.x} y2={needleEnd.y}
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          style={{ transformOrigin: "100px 100px", transition: "all 0.8s cubic-bezier(.34,1.56,.64,1)" }}
        />
        <circle cx="100" cy="100" r="6" fill={color} />

        {/* Score text */}
        <text x="100" y="90" textAnchor="middle" fontSize="22" fontWeight="700" fill={color}>
          {clamped}
        </text>
        <text x="100" y="105" textAnchor="middle" fontSize="9" fill="#94a3b8">
          CREDIBILITY SCORE
        </text>
      </svg>
      <span
        className="text-sm font-bold tracking-widest uppercase px-4 py-1 rounded-full"
        style={{ color, background: color + "22", border: `1px solid ${color}44` }}
      >
        {getLabel(clamped)}
      </span>
    </div>
  );
}

// ─── Probability Badge ─────────────────────────────────────────────────────────
function ProbBadge({ label }) {
  const map = {
    "Low":       { bg: "#22c55e22", border: "#22c55e44", text: "#22c55e" },
    "Moderate":  { bg: "#eab30822", border: "#eab30844", text: "#eab308" },
    "High":      { bg: "#f9731622", border: "#f9731644", text: "#f97316" },
    "Very High": { bg: "#ef444422", border: "#ef444444", text: "#ef4444" },
  };
  const s = map[label] || map["Moderate"];
  return (
    <div
      className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold"
      style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.text }}
    >
      <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: s.text }} />
      Misinformation Risk: {label}
    </div>
  );
}

// ─── Claim Card ────────────────────────────────────────────────────────────────
function ClaimCard({ claim, index }) {
  const score = claim.credibility_score;
  const color = score >= 70 ? "#22c55e" : score >= 50 ? "#eab308" : score >= 30 ? "#f97316" : "#ef4444";

  return (
    <div
      className="relative rounded-xl p-4 border"
      style={{ borderColor: color + "44", background: color + "08" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <span
            className="text-xs font-bold uppercase tracking-wider"
            style={{ color: "#94a3b8" }}
          >
            Claim {index + 1}
          </span>
          <p className="mt-1 text-sm text-slate-200 leading-relaxed">{claim.claim}</p>
        </div>
        <div className="flex flex-col items-center shrink-0 ml-2">
          <span className="text-xl font-black" style={{ color }}>{score}</span>
          <span className="text-xs" style={{ color: "#94a3b8" }}>/100</span>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{ background: color + "22", color }}
        >
          {claim.assessment}
        </span>
        {/* Mini score bar */}
        <div className="w-24 h-1.5 rounded-full bg-slate-700 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${score}%`, background: color }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Source Link ───────────────────────────────────────────────────────────────
function SourceLink({ url, index }) {
  const isURL = url.startsWith("http");
  return (
    <a
      href={isURL ? url : undefined}
      target={isURL ? "_blank" : undefined}
      rel="noopener noreferrer"
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-slate-200 transition-colors"
      style={{ background: "#1e293b", border: "1px solid #334155" }}
    >
      <span
        className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
        style={{ background: "#0ea5e922", color: "#0ea5e9" }}
      >
        {index + 1}
      </span>
      <span className="truncate max-w-xs">{url}</span>
    </a>
  );
}

// ─── Loading State ─────────────────────────────────────────────────────────────
function LoadingOverlay() {
  const steps = [
    "Extracting factual claims…",
    "Searching knowledge base…",
    "Retrieving trusted sources…",
    "Reasoning with LLM…",
    "Generating report…",
  ];
  const [step, setStep] = useState(0);
  useState(() => {
    const iv = setInterval(() => setStep((s) => Math.min(s + 1, steps.length - 1)), 900);
    return () => clearInterval(iv);
  });
  return (
    <div className="flex flex-col items-center gap-6 py-12">
      {/* Animated rings */}
      <div className="relative w-20 h-20">
        <div className="absolute inset-0 rounded-full border-2 border-cyan-500 opacity-20 animate-ping" />
        <div className="absolute inset-2 rounded-full border-2 border-cyan-400 opacity-40 animate-ping" style={{ animationDelay: "0.3s" }} />
        <div className="absolute inset-4 rounded-full border-2 border-cyan-300 animate-spin" style={{ borderTopColor: "transparent" }} />
        <div
          className="absolute inset-0 flex items-center justify-center text-2xl"
          style={{ filter: "drop-shadow(0 0 8px #0ea5e9)" }}
        >
          🔍
        </div>
      </div>
      <div className="text-center">
        <p className="text-slate-400 text-sm font-medium mb-1" style={{ fontFamily: "'Courier New', monospace" }}>
          {steps[step]}
        </p>
        <div className="flex gap-1 justify-center mt-3">
          {steps.map((_, i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full transition-all duration-300"
              style={{ background: i <= step ? "#0ea5e9" : "#334155" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("claims");
  const resultRef = useRef(null);

  const handleAnalyze = async () => {
    const trimmed = text.trim();
    if (!trimmed || trimmed.length < 30) {
      setError("Please enter at least one full sentence of text to analyze.");
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await analyzeText(trimmed, url.trim() || null);
      setResult(data);
      setActiveTab("claims");
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (e) {
      setError(e.message || "Analysis failed. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const charCount = text.length;
  const charMax = 15000;

  return (
    <div
      className="min-h-screen text-slate-100"
      style={{
        background: "radial-gradient(ellipse at 20% 0%, #0c1a2e 0%, #0a0f1a 50%, #050810 100%)",
        fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
      }}
    >
      {/* Noise texture overlay */}
      <div
        className="fixed inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.15'/%3E%3C/svg%3E")`,
          backgroundSize: "150px 150px",
        }}
      />

      {/* Decorative glows */}
      <div className="fixed top-0 left-1/4 w-96 h-96 rounded-full pointer-events-none"
        style={{ background: "#0ea5e908", filter: "blur(80px)" }} />
      <div className="fixed bottom-0 right-1/4 w-96 h-96 rounded-full pointer-events-none"
        style={{ background: "#6366f108", filter: "blur(100px)" }} />

      <div className="relative max-w-3xl mx-auto px-4 py-12">

        {/* ── Header ── */}
        <header className="text-center mb-14">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
              style={{
                background: "linear-gradient(135deg, #0ea5e9, #6366f1)",
                boxShadow: "0 0 24px #0ea5e940",
              }}
            >
              🔎
            </div>
            <h1
              className="text-4xl font-black tracking-tight"
              style={{
                background: "linear-gradient(90deg, #e2e8f0, #0ea5e9 50%, #818cf8)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                fontFamily: "'DM Serif Display', Georgia, serif",
                letterSpacing: "-0.02em",
              }}
            >
              TruthLens AI
            </h1>
          </div>
          <p className="text-slate-400 text-base max-w-md mx-auto leading-relaxed">
            Paste any news article or social media post below.
            Our LLM + RAG pipeline will extract claims, verify them against
            trusted sources, and return a credibility report.
          </p>
          <div className="flex items-center justify-center gap-6 mt-5 text-xs text-slate-500">
            {["Claim Extraction", "Vector Retrieval", "LLM Reasoning"].map((t, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
                {t}
              </span>
            ))}
          </div>
        </header>

        {/* ── Input Card ── */}
        <div
          className="rounded-2xl p-6 mb-6"
          style={{
            background: "rgba(15,23,42,0.8)",
            border: "1px solid rgba(148,163,184,0.1)",
            backdropFilter: "blur(12px)",
            boxShadow: "0 25px 50px rgba(0,0,0,0.4)",
          }}
        >
          {/* Optional URL */}
          <div className="mb-4">
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Article URL (optional)
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/news-article"
              className="w-full px-4 py-2.5 rounded-xl text-sm text-slate-200 placeholder-slate-600 focus:outline-none transition-all"
              style={{
                background: "#0f172a",
                border: "1px solid rgba(148,163,184,0.12)",
                caretColor: "#0ea5e9",
              }}
              onFocus={(e) => (e.target.style.borderColor = "#0ea5e966")}
              onBlur={(e) => (e.target.style.borderColor = "rgba(148,163,184,0.12)")}
            />
          </div>

          {/* Text area */}
          <div className="mb-5">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Article Text
              </label>
              <span
                className="text-xs tabular-nums"
                style={{ color: charCount > charMax * 0.9 ? "#f97316" : "#475569" }}
              >
                {charCount.toLocaleString()} / {charMax.toLocaleString()}
              </span>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your news article, tweet, or social media post here…"
              rows={7}
              maxLength={charMax}
              className="w-full px-4 py-3 rounded-xl text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none transition-all leading-relaxed"
              style={{
                background: "#0f172a",
                border: "1px solid rgba(148,163,184,0.12)",
                caretColor: "#0ea5e9",
              }}
              onFocus={(e) => (e.target.style.borderColor = "#0ea5e966")}
              onBlur={(e) => (e.target.style.borderColor = "rgba(148,163,184,0.12)")}
            />
          </div>

          {/* Error */}
          {error && (
            <div
              className="mb-4 px-4 py-3 rounded-xl text-sm text-red-300 flex items-start gap-2"
              style={{ background: "#ef444418", border: "1px solid #ef444433" }}
            >
              <span className="mt-0.5">⚠</span> {error}
            </div>
          )}

          {/* Analyze Button */}
          <button
            onClick={handleAnalyze}
            disabled={loading || text.trim().length < 30}
            className="w-full py-3.5 rounded-xl font-bold text-sm tracking-wide uppercase transition-all duration-200 relative overflow-hidden"
            style={{
              background: loading || text.trim().length < 30
                ? "#1e293b"
                : "linear-gradient(135deg, #0ea5e9, #6366f1)",
              color: loading || text.trim().length < 30 ? "#475569" : "#fff",
              boxShadow: loading || text.trim().length < 30
                ? "none"
                : "0 0 30px #0ea5e940",
              cursor: loading || text.trim().length < 30 ? "not-allowed" : "pointer",
            }}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Analyzing…
              </span>
            ) : (
              "Analyze for Misinformation →"
            )}
          </button>
        </div>

        {/* ── Loading ── */}
        {loading && (
          <div
            className="rounded-2xl p-6 mb-6"
            style={{
              background: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(148,163,184,0.08)",
            }}
          >
            <LoadingOverlay />
          </div>
        )}

        {/* ── Results ── */}
        {result && !loading && (
          <div ref={resultRef} className="space-y-6">

            {/* Score card */}
            <div
              className="rounded-2xl p-6"
              style={{
                background: "rgba(15,23,42,0.9)",
                border: "1px solid rgba(148,163,184,0.1)",
                boxShadow: "0 25px 50px rgba(0,0,0,0.4)",
              }}
            >
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className="shrink-0">
                  <CredibilityMeter score={result.credibility_score} />
                </div>
                <div className="flex-1 text-center md:text-left">
                  <ProbBadge label={result.misinformation_probability} />
                  <p className="mt-4 text-sm text-slate-300 leading-relaxed">
                    {result.explanation}
                  </p>
                  <p className="mt-3 text-xs text-slate-500">
                    Analyzed {result.claims?.length || 0} claims ·{" "}
                    {result.sources?.length || 0} sources retrieved ·{" "}
                    {result.processing_time_ms}ms
                  </p>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "rgba(15,23,42,0.9)",
                border: "1px solid rgba(148,163,184,0.1)",
              }}
            >
              {/* Tab bar */}
              <div
                className="flex"
                style={{ borderBottom: "1px solid rgba(148,163,184,0.1)" }}
              >
                {["claims", "sources"].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className="px-6 py-3.5 text-sm font-semibold capitalize transition-all"
                    style={{
                      color: activeTab === tab ? "#0ea5e9" : "#64748b",
                      borderBottom: activeTab === tab ? "2px solid #0ea5e9" : "2px solid transparent",
                      background: "transparent",
                    }}
                  >
                    {tab === "claims"
                      ? `Claims (${result.claims?.length || 0})`
                      : `Sources (${result.sources?.length || 0})`}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="p-5">
                {activeTab === "claims" && (
                  <div className="space-y-3">
                    {result.claims && result.claims.length > 0 ? (
                      result.claims.map((c, i) => (
                        <ClaimCard key={i} claim={c} index={i} />
                      ))
                    ) : (
                      <p className="text-slate-500 text-sm text-center py-6">
                        No individual claims extracted.
                      </p>
                    )}
                  </div>
                )}
                {activeTab === "sources" && (
                  <div className="space-y-2">
                    {result.sources && result.sources.length > 0 ? (
                      result.sources.map((s, i) => (
                        <SourceLink key={i} url={s} index={i} />
                      ))
                    ) : (
                      <p className="text-slate-500 text-sm text-center py-6">
                        No sources retrieved.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Re-analyze button */}
            <button
              onClick={() => { setResult(null); setError(null); window.scrollTo({ top: 0, behavior: "smooth" }); }}
              className="w-full py-3 rounded-xl text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors"
              style={{ background: "rgba(15,23,42,0.5)", border: "1px solid rgba(148,163,184,0.08)" }}
            >
              ← Analyze another article
            </button>
          </div>
        )}

        {/* ── Footer ── */}
        <footer className="mt-16 text-center text-xs text-slate-600">
          TruthLens AI · Powered by LLM + RAG · Not a substitute for professional fact-checking
        </footer>
      </div>
    </div>
  );
}
