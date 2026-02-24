"""
FastAPI application entry point for the NVDA Earnings War Room.

Wires together all application components: CORS middleware, route registration,
FMP client, Polymarket client, SocialData client, in-memory cache, and the
background data refresh scheduler.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.cache import cache
from backend.fmp_client import FMPClient
from backend.polymarket_client import PolymarketClient
from backend.socialdata_client import SocialDataClient
from backend.scheduler import init_scheduler

# ---------------------------------------------------------------------------
# Logging — configured at module level before anything else runs
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — manages startup and shutdown of long-lived resources
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle: initialise shared resources on startup,
    tear them down cleanly on shutdown.

    Startup sequence:
      1. Create FMPClient and store on ``app.state``.
      2. Create PolymarketClient and store on ``app.state``.
      3. Create SocialDataClient and store on ``app.state``.
      4. Initialise and store the DataRefreshScheduler on ``app.state``.
      5. Start the scheduler so background refresh tasks begin immediately.
      6. Log that the application is ready to serve requests.

    Shutdown sequence:
      1. Stop the scheduler, cancelling all background tasks.
      2. Close the PolymarketClient.
      3. Close the SocialDataClient.
      4. Close the FMPClient (drains the underlying httpx connection pool).
      5. Clear the in-memory cache.
      6. Log that the application has shut down.
    """
    # ------------------------------------------------------------------
    # STARTUP
    # ------------------------------------------------------------------
    logger.info("Starting NVDA Earnings War Room …")

    fmp_client: FMPClient = FMPClient()
    app.state.fmp_client = fmp_client

    polymarket_client: PolymarketClient = PolymarketClient()
    app.state.polymarket_client = polymarket_client

    socialdata_client: SocialDataClient = SocialDataClient()
    app.state.socialdata_client = socialdata_client

    scheduler = init_scheduler(fmp_client, polymarket_client, socialdata_client)
    app.state.scheduler = scheduler

    await scheduler.start()

    logger.info("NVDA Earnings War Room startup complete — serving requests")

    yield  # application runs here

    # ------------------------------------------------------------------
    # SHUTDOWN
    # ------------------------------------------------------------------
    logger.info("Shutting down NVDA Earnings War Room …")

    await scheduler.stop()
    await polymarket_client.close()
    await socialdata_client.close()
    await fmp_client.close()
    await cache.clear()

    logger.info("NVDA Earnings War Room shutdown complete")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NVDA Earnings War Room",
    description="Real-time NVDA earnings data dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Route registration — wrapped in try/except so the app starts even when
# individual route modules have not been implemented yet.
# ---------------------------------------------------------------------------
try:
    from backend.routes.price import router as price_router
    app.include_router(price_router, prefix="/api/price", tags=["price"])
    logger.debug("Registered price router at /api/price")
except ImportError:
    logger.warning("Price route not available — module not yet implemented")

try:
    from backend.routes.options import router as options_router
    app.include_router(options_router, prefix="/api/options", tags=["options"])
    logger.debug("Registered options router at /api/options")
except ImportError:
    logger.warning("Options route not available — module not yet implemented")

try:
    from backend.routes.earnings import router as earnings_router
    app.include_router(earnings_router, prefix="/api/earnings", tags=["earnings"])
    logger.debug("Registered earnings router at /api/earnings")
except ImportError:
    logger.warning("Earnings route not available — module not yet implemented")

try:
    from backend.routes.sentiment import router as sentiment_router
    app.include_router(sentiment_router, prefix="/api/sentiment", tags=["sentiment"])
    logger.debug("Registered sentiment router at /api/sentiment")
except ImportError:
    logger.warning("Sentiment route not available — module not yet implemented")

try:
    from backend.routes.hyperscaler import router as hyperscaler_router
    app.include_router(hyperscaler_router, prefix="/api/hyperscaler", tags=["hyperscaler"])
    logger.debug("Registered hyperscaler router at /api/hyperscaler")
except ImportError:
    logger.warning("Hyperscaler route not available — module not yet implemented")

try:
    from backend.routes.predictions import router as predictions_router
    app.include_router(predictions_router, prefix="/api/predictions", tags=["predictions"])
    logger.debug("Registered predictions router at /api/predictions")
except ImportError:
    logger.warning("Predictions route not available — module not yet implemented")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return service liveness status."""
    return {"status": "ok", "service": "nvda-war-room"}
