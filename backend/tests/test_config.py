"""
Tests for configuration management.
Verifies environment variable loading, validation, and defaults.
"""

import os
from typing import Any, Dict
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from backend.config import Settings, get_settings


class TestSettings:
    """Test suite for Settings class."""

    def test_missing_api_key_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing FMP_API_KEY raises ValidationError."""
        monkeypatch.delenv("FMP_API_KEY", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["loc"] == ("fmp_api_key",) for err in errors)
        assert any("field required" in str(err["msg"]).lower() for err in errors)

    def test_empty_api_key_raises_error(self) -> None:
        """Test that empty FMP_API_KEY raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(fmp_api_key="")
        
        errors = exc_info.value.errors()
        assert any(
            err["loc"] == ("fmp_api_key",) and "must not be empty" in str(err["msg"])
            for err in errors
        )

    def test_whitespace_api_key_raises_error(self) -> None:
        """Test that whitespace-only FMP_API_KEY raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(fmp_api_key="   ")
        
        errors = exc_info.value.errors()
        assert any(
            err["loc"] == ("fmp_api_key",) and "must not be empty" in str(err["msg"])
            for err in errors
        )

    def test_valid_api_key_is_stripped(self) -> None:
        """Test that API key whitespace is stripped."""
        settings = Settings(fmp_api_key="  test-key-123  ")
        assert settings.fmp_api_key == "test-key-123"

    def test_default_fmp_base_url(self) -> None:
        """Test that FMP_BASE_URL has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.fmp_base_url == "https://financialmodelingprep.com/api"

    def test_custom_fmp_base_url(self) -> None:
        """Test that custom FMP_BASE_URL is accepted."""
        settings = Settings(
            fmp_api_key="test-key",
            fmp_base_url="https://custom.api.com/v1"
        )
        assert settings.fmp_base_url == "https://custom.api.com/v1"

    def test_fmp_base_url_trailing_slash_removed(self) -> None:
        """Test that trailing slash is removed from base URL."""
        settings = Settings(
            fmp_api_key="test-key",
            fmp_base_url="https://api.example.com/"
        )
        assert settings.fmp_base_url == "https://api.example.com"

    def test_invalid_fmp_base_url_raises_error(self) -> None:
        """Test that invalid base URL raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                fmp_api_key="test-key",
                fmp_base_url="not-a-url"
            )
        
        errors = exc_info.value.errors()
        assert any(
            err["loc"] == ("fmp_base_url",) and "must start with http" in str(err["msg"]).lower()
            for err in errors
        )

    def test_default_risk_free_rate(self) -> None:
        """Test that risk_free_rate has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.risk_free_rate == 0.045

    def test_custom_risk_free_rate(self) -> None:
        """Test that custom risk_free_rate is accepted."""
        settings = Settings(fmp_api_key="test-key", risk_free_rate=0.05)
        assert settings.risk_free_rate == 0.05

    def test_risk_free_rate_string_coercion(self) -> None:
        """Test that risk_free_rate string is coerced to float."""
        settings = Settings(fmp_api_key="test-key", risk_free_rate="0.055")
        assert settings.risk_free_rate == 0.055
        assert isinstance(settings.risk_free_rate, float)

    def test_risk_free_rate_validation_negative(self) -> None:
        """Test that negative risk_free_rate raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(fmp_api_key="test-key", risk_free_rate=-0.01)

    def test_risk_free_rate_validation_too_high(self) -> None:
        """Test that risk_free_rate > 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(fmp_api_key="test-key", risk_free_rate=1.5)

    def test_default_cache_ttl_price(self) -> None:
        """Test that cache_ttl_price has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.cache_ttl_price == 5

    def test_default_cache_ttl_options(self) -> None:
        """Test that cache_ttl_options has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.cache_ttl_options == 60

    def test_default_cache_ttl_sentiment(self) -> None:
        """Test that cache_ttl_sentiment has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.cache_ttl_sentiment == 900

    def test_default_cache_ttl_earnings(self) -> None:
        """Test that cache_ttl_earnings has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.cache_ttl_earnings == 86400

    def test_default_cache_ttl_hyperscaler(self) -> None:
        """Test that cache_ttl_hyperscaler has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.cache_ttl_hyperscaler == 86400

    def test_custom_cache_ttl_values(self) -> None:
        """Test that custom cache TTL values are accepted."""
        settings = Settings(
            fmp_api_key="test-key",
            cache_ttl_price=10,
            cache_ttl_options=120,
            cache_ttl_sentiment=1800,
            cache_ttl_earnings=172800,
            cache_ttl_hyperscaler=259200,
        )
        assert settings.cache_ttl_price == 10
        assert settings.cache_ttl_options == 120
        assert settings.cache_ttl_sentiment == 1800
        assert settings.cache_ttl_earnings == 172800
        assert settings.cache_ttl_hyperscaler == 259200

    def test_cache_ttl_string_coercion(self) -> None:
        """Test that cache TTL strings are coerced to int."""
        settings = Settings(
            fmp_api_key="test-key",
            cache_ttl_price="15",
        )
        assert settings.cache_ttl_price == 15
        assert isinstance(settings.cache_ttl_price, int)

    def test_cache_ttl_validation_too_low(self) -> None:
        """Test that cache TTL < 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(fmp_api_key="test-key", cache_ttl_price=0)

    def test_default_log_level(self) -> None:
        """Test that log_level has correct default."""
        settings = Settings(fmp_api_key="test-key")
        assert settings.log_level == "INFO"

    def test_custom_log_level(self) -> None:
        """Test that custom log_level is accepted."""
        settings = Settings(fmp_api_key="test-key", log_level="DEBUG")
        assert settings.log_level == "DEBUG"

    @patch.dict(os.environ, {
        "FMP_API_KEY": "env-test-key",
        "FMP_BASE_URL": "https://env.api.com",
        "RISK_FREE_RATE": "0.05",
        "CACHE_TTL_PRICE": "10",
        "CACHE_TTL_OPTIONS": "120",
        "LOG_LEVEL": "DEBUG",
    }, clear=True)
    def test_loads_from_environment(self) -> None:
        """Test that settings are loaded from environment variables."""
        # Clear the cache to force reload
        get_settings.cache_clear()
        
        settings = Settings()
        assert settings.fmp_api_key == "env-test-key"
        assert settings.fmp_base_url == "https://env.api.com"
        assert settings.risk_free_rate == 0.05
        assert settings.cache_ttl_price == 10
        assert settings.cache_ttl_options == 120
        assert settings.log_level == "DEBUG"

    def test_get_settings_returns_cached_instance(self) -> None:
        """Test that get_settings returns the same instance."""
        get_settings.cache_clear()
        
        with patch.dict(os.environ, {"FMP_API_KEY": "cached-key"}, clear=True):
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_all_fields_have_type_hints(self) -> None:
        """Test that all Settings fields have proper type hints."""
        # Get field annotations
        annotations = Settings.__annotations__
        
        # Check that key fields exist and have correct types
        assert "fmp_api_key" in annotations
        assert "fmp_base_url" in annotations
        assert "risk_free_rate" in annotations
        assert "cache_ttl_price" in annotations
        assert "cache_ttl_options" in annotations
        assert "cache_ttl_sentiment" in annotations
        assert "cache_ttl_earnings" in annotations
        assert "cache_ttl_hyperscaler" in annotations
        assert "log_level" in annotations
        
        # Verify types
        assert annotations["fmp_api_key"] == str
        assert annotations["fmp_base_url"] == str
        assert annotations["risk_free_rate"] == float
        assert annotations["cache_ttl_price"] == int
        assert annotations["cache_ttl_options"] == int
        assert annotations["cache_ttl_sentiment"] == int
        assert annotations["cache_ttl_earnings"] == int
        assert annotations["cache_ttl_hyperscaler"] == int

    def test_no_any_type_in_annotations(self) -> None:
        """Test that no fields use Any type."""
        from typing import get_args, get_origin
        
        annotations = Settings.__annotations__
        for field_name, field_type in annotations.items():
            # Check the field type itself
            assert field_type != Any, f"Field {field_name} uses Any type"
            
            # Check generic args (e.g., Literal["DEBUG", ...])
            origin = get_origin(field_type)
            if origin is not None:
                args = get_args(field_type)
                for arg in args:
                    assert arg != Any, f"Field {field_name} has Any in type args"