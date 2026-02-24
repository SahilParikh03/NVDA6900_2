EM = chr(0x2014)
AR = chr(0x2192)
EN = chr(0x2013)
BT = chr(96)
DQ = chr(34)
SQ = chr(39)
DS = chr(36)

fp = "C:/Users/ReachElysium/Documents/NVDA6900_2/source_of_truth.md"
with open(fp, "r", encoding="utf-8") as f:
    c = f.read()
orig = len(c)
ok, fail = [], []

def p(old, new, label):
    global c
    if old in c:
        c = c.replace(old, new, 1)
        ok.append(label)
    else:
        fail.append("MISSING: " + label)

old_s10 = (
    "## 10. OPEN QUESTIONS (Flag if encountered)

"
    "- Does the FMP Starter plan actually include the options chain endpoint? (Validate in Phase 1)
"
    "- Does FMP provide implied volatility per contract, or do we need to calculate it? (Validate in Phase 1)
"
    "- What is the exact rate limit on the Starter plan? (Document in Phase 1)
"
    "- Does the social sentiment endpoint return NVDA-specific data or just general market sentiment? (Validate in Phase 1)
"
    "- Are earnings call transcripts full-text or summary-only on the Starter plan? (Validate in Phase 1)"
)

new_s10 = (
    "## 10. RESOLVED QUESTIONS (Phase 1" + EN + "2.5)

"
    "- **Options chain:** FMP dropped this endpoint entirely from the stable API. **Resolution:** Replaced with Polymarket probability heatmap.
"
    "- **Social sentiment:** FMP removed the " + BT + "/v4/social-sentiments" + BT + " endpoint. **Resolution:** Replaced with SocialData.tools Twitter/X search.
"
    "- **Earnings surprises:** FMP returns 404 for per-symbol surprises on stable API. **Resolution:** Signal removed from predictions engine.
"
    "- **Earnings transcripts:** FMP returns 402 (requires higher plan). **Resolution:** Engine exists but runs with empty data. Upgrade FMP plan or find alternative provider to enable.
"
    "- **Quarterly analyst estimates:** FMP returns 402. **Resolution:** Annual estimates only.
"
    "- **Rate limits:** FMP stable API returns 429 on rate limit. Backend implements exponential backoff with 3 retries.
"
    "- **Implied volatility:** FMP did provide IV per contract, but options chain is now unavailable. Bisection method in gex_engine.py exists but has no live data feed."
)

p(old_s10, new_s10, "Section10")

old_footer = "*Last updated: February 23, 2026*
*Version: 1.0 " + EM + " MVP*"
new_footer = "*Last updated: February 24, 2026*
*Version: 1.1 " + EM + " Post-Data-Migration*"
p(old_footer, new_footer, "Footer")

p(
    "CACHE_TTL_HYPERSCALER=86400

# Frontend",
    "CACHE_TTL_HYPERSCALER=86400
SOCIALDATA_API_KEY=your_socialdata_api_key_here
CACHE_TTL_SOCIAL=60
CACHE_TTL_POLYMARKET=30

# Frontend",
    "EnvVars"
)

old_gloss = "| **Hyperscaler** | Large cloud providers (MSFT, AMZN, GOOGL, META) who are NVDA" + SQ + "s biggest data center customers |"
new_gloss = (
    old_gloss + "
"
    "| **Polymarket** | Decentralized prediction market platform. Binary YES/NO markets provide implied probabilities for NVDA price levels |
"
    "| **SocialData.tools** | Third-party API providing Twitter/X search access. Used for social sentiment analysis |
"
    "| **Probability Heatmap** | Visual representation of implied probabilities at different NVDA price strikes, derived from Polymarket prediction markets |"
)
p(old_gloss, new_gloss, "Glossary")

print("OK:", ok)
print("FAIL:", fail)
print("Length:", orig, "->", len(c))

with open(fp, "w", encoding="utf-8") as f:
    f.write(c)
print("Written.")

# Verify
lines_out = c.splitlines()
print("--- FIRST 5 ---")
for ln in lines_out[:5]: print(repr(ln))
print("--- LAST 5 ---")
for ln in lines_out[-5:]: print(repr(ln))