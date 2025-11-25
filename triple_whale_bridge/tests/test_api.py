"""Tests for Triple Whale API client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from triple_whale_bridge.core.api import (
    TripleWhaleClient,
    TripleWhaleConfig,
    TripleWhaleAPIError,
    TripleWhaleAuthError,
    TripleWhaleRateLimitError,
    TripleWhaleValidationError,
)
from triple_whale_bridge.core.schema import (
    TripleWhaleEvent,
    TripleWhaleEventType,
    TripleWhaleEventProperties,
)


class TestTripleWhaleConfig:
    """Tests for Triple Whale configuration."""

    def test_config_from_env(self, monkeypatch):
        """Test loading config from environment."""
        monkeypatch.setenv("TRIPLE_WHALE_API_KEY", "test_key_123")
        monkeypatch.setenv("TRIPLE_WHALE_TIMEOUT", "60")

        config = TripleWhaleConfig.from_env()

        assert config.api_key == "test_key_123"
        assert config.timeout == 60.0
        assert config.base_url == "https://api.triplewhale.com/api/v2"

    def test_config_missing_api_key(self, monkeypatch):
        """Test error when API key is missing."""
        monkeypatch.delenv("TRIPLE_WHALE_API_KEY", raising=False)

        with pytest.raises(ValueError, match="TRIPLE_WHALE_API_KEY"):
            TripleWhaleConfig.from_env()


class TestTripleWhaleClient:
    """Tests for Triple Whale API client."""

    @pytest.fixture
    def client(self):
        """Create client with test config."""
        config = TripleWhaleConfig(api_key="test_api_key")
        return TripleWhaleClient(config)

    @pytest.fixture
    def sample_event(self):
        """Create sample event for testing."""
        return TripleWhaleEvent(
            type=TripleWhaleEventType.MQL,
            email="test@example.com",
            properties=TripleWhaleEventProperties(
                pipeline_name="Sales",
                lead_value=5000,
            )
        )

    @pytest.mark.asyncio
    async def test_send_event_success(self, client, sample_event):
        """Test successful event sending."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}

        with patch.object(client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.send_event(sample_event)

            assert result["status"] == "success"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_event_missing_identifier(self, client):
        """Test error when event has no email or phone."""
        event = TripleWhaleEvent(
            type=TripleWhaleEventType.LEAD,
            email=None,
            phone=None,
        )

        with pytest.raises(TripleWhaleValidationError, match="email or phone"):
            await client.send_event(event)

    @pytest.mark.asyncio
    async def test_send_event_auth_error(self, client, sample_event):
        """Test handling of authentication errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"

        with patch.object(client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(TripleWhaleAuthError):
                await client.send_event(sample_event)

    @pytest.mark.asyncio
    async def test_send_event_rate_limit(self, client, sample_event):
        """Test handling of rate limit errors."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch.object(client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(TripleWhaleRateLimitError):
                await client.send_event(sample_event)

    @pytest.mark.asyncio
    async def test_send_event_validation_error(self, client, sample_event):
        """Test handling of validation errors."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Invalid payload"

        with patch.object(client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(TripleWhaleValidationError):
                await client.send_event(sample_event)

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, client, sample_event):
        """Test retry logic on 5xx errors."""
        # First call fails, second succeeds
        mock_fail = MagicMock()
        mock_fail.status_code = 503
        mock_fail.text = "Service unavailable"

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"status": "success"}

        with patch.object(client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_fail, mock_success]

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await client.send_event(sample_event)

            assert result["status"] == "success"
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client works as async context manager."""
        config = TripleWhaleConfig(api_key="test_key")

        async with TripleWhaleClient(config) as client:
            assert client is not None
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_validate_api_key(self, client):
        """Test API key validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"valid": True, "scopes": ["orders:write"]}

        with patch.object(client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.validate_api_key()

            assert result["valid"] is True
