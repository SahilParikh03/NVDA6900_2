"""
Configuration management using Pydantic Settings.
Loads environment variables and provides centralized constants.
"""

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    fmp_api_key: str = Field(
        ...,
        description="Financial Modeling Prep API key (required)",
    )
    fmp_base_url: str = Field(
        default="https://financialmodelingprep.com/api",
        description="Base URL for FMP API",
    )
    socialdata_api_key: str = Field(
        default="",
        description="SocialData.tools API key for Twitter search",
    )

    # Financial Constants
    risk_free_rate: float = Field(
        default=0.045,
        ge=0.0,
        le=1.0,
        description="Risk-free rate for options pricing (0-1)",
    )

    # Cache TTL Settings (seconds)
    cache_ttl_price: int = Field(
        default=5,
        ge=1,
        description="Cache TTL for price data in seconds",
    )
    cache_ttl_options: int = Field(
        default=60,
        ge=1,
        description="Cache TTL for options data in seconds",
    )
    cache_ttl_sentiment: int = Field(
        default=900,
        ge=1,
        description="Cache TTL for sentiment data in seconds",
    )
    cache_ttl_earnings: int = Field(
        default=86400,
        ge=1,
        description="Cache TTL for earnings data in seconds",
    )
    cache_ttl_hyperscaler: int = Field(
        default=86400,
        ge=1,
        description="Cache TTL for hyperscaler data in seconds",
    )
    cache_ttl_social: int = Field(
        default=60,
        ge=1,
        description="Cache TTL for social media data in seconds",
    )
    cache_ttl_polymarket: int = Field(
        default=30,
        ge=1,
        description="Cache TTL for Polymarket data in seconds",
    )

    # Application Constants
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    @field_validator("fmp_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Ensure API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError("FMP_API_KEY must not be empty")
        return v.strip()

    @field_validator("fmp_base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base URL is properly formatted."""
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("FMP_BASE_URL must start with http:// or https://")
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings singleton
        
    Raises:
        ValidationError: If required environment variables are missing or invalid
    """
    return Settings()


# Singleton instance for import
settings = get_settings()