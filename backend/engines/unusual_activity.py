"""
Unusual Options Activity Scanner.

Identifies options strikes with abnormally high volume relative to open
interest. A contract is flagged as unusual when:
  - vol_oi_ratio > VOL_OI_RATIO_THRESHOLD (2.0)
  - volume > MIN_VOLUME_FILTER (1000)

The top MAX_UNUSUAL_RESULTS (20) results are returned, sorted by
vol_oi_ratio descending.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants (no magic numbers in engine logic)
# ---------------------------------------------------------------------------
VOL_OI_RATIO_THRESHOLD: float = 2.0
MIN_VOLUME_FILTER: int = 1000
MAX_UNUSUAL_RESULTS: int = 20


# ---------------------------------------------------------------------------
# Output schemas (Pydantic v2)
# ---------------------------------------------------------------------------
class UnusualContract(BaseModel):
    """A single options contract flagged as having unusual activity."""

    strike: float
    expiration: str
    type: str  # "CALL" or "PUT"
    volume: int
    open_interest: int
    vol_oi_ratio: float = Field(..., description="volume / open_interest")
    implied_volatility: float
    last_price: float


class UnusualActivityResult(BaseModel):
    """Full result from the unusual activity scanner."""

    unusual_activity: list[UnusualContract]
    total_unusual_contracts: int = Field(
        ..., description="Count of all flagged contracts before top-N truncation"
    )
    put_call_ratio_unusual: float = Field(
        ...,
        description=(
            "Puts / Calls among flagged contracts. "
            "0.0 when there are no calls or no flagged contracts."
        ),
    )
    last_updated: str = Field(..., description="ISO-8601 UTC timestamp")


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
async def scan_unusual_activity(
    options_chain: list[dict],
) -> UnusualActivityResult:
    """
    Scan an options chain for contracts with abnormally high volume/OI ratios.

    Args:
        options_chain: Raw list of option contract dicts from FMP.

    Returns:
        UnusualActivityResult with flagged contracts and aggregate stats.
    """
    now_utc: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not options_chain:
        logger.info("scan_unusual_activity: received empty options chain")
        return UnusualActivityResult(
            unusual_activity=[],
            total_unusual_contracts=0,
            put_call_ratio_unusual=0.0,
            last_updated=now_utc,
        )

    flagged: list[UnusualContract] = []

    for contract in options_chain:
        open_interest: int = int(contract.get("openInterest") or 0)
        volume: int = int(contract.get("volume") or 0)

        # Skip contracts that would cause division-by-zero or fail thresholds
        if open_interest <= 0:
            logger.debug(
                "Skipping contract strike=%s exp=%s: zero/missing open interest",
                contract.get("strike"),
                contract.get("expirationDate"),
            )
            continue

        if volume <= 0:
            logger.debug(
                "Skipping contract strike=%s exp=%s: zero/missing volume",
                contract.get("strike"),
                contract.get("expirationDate"),
            )
            continue

        vol_oi_ratio: float = volume / open_interest

        if vol_oi_ratio > VOL_OI_RATIO_THRESHOLD and volume > MIN_VOLUME_FILTER:
            contract_type: str = str(contract.get("type", "")).upper()
            flagged.append(
                UnusualContract(
                    strike=float(contract.get("strike", 0.0)),
                    expiration=str(contract.get("expirationDate", "")),
                    type=contract_type,
                    volume=volume,
                    open_interest=open_interest,
                    vol_oi_ratio=round(vol_oi_ratio, 4),
                    implied_volatility=float(
                        contract.get("impliedVolatility") or 0.0
                    ),
                    last_price=float(contract.get("lastPrice") or 0.0),
                )
            )

    total_unusual: int = len(flagged)
    logger.info(
        "scan_unusual_activity: %d unusual contracts found (threshold ratio=%.1f, min_vol=%d)",
        total_unusual,
        VOL_OI_RATIO_THRESHOLD,
        MIN_VOLUME_FILTER,
    )

    # Sort by vol_oi_ratio descending, then return top N
    flagged.sort(key=lambda c: c.vol_oi_ratio, reverse=True)
    top_results: list[UnusualContract] = flagged[:MAX_UNUSUAL_RESULTS]

    # Put/call ratio among ALL flagged contracts (not just top N)
    puts: int = sum(1 for c in flagged if c.type == "PUT")
    calls: int = sum(1 for c in flagged if c.type == "CALL")
    put_call_ratio: float = (puts / calls) if calls > 0 else 0.0

    return UnusualActivityResult(
        unusual_activity=top_results,
        total_unusual_contracts=total_unusual,
        put_call_ratio_unusual=round(put_call_ratio, 4),
        last_updated=now_utc,
    )
