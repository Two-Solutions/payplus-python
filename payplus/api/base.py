"""
Base API class for PayPlus endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from payplus.client import PayPlus


class BaseAPI:
    """Base class for API endpoints."""
    
    def __init__(self, client: "PayPlus"):
        self._client = client
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a synchronous API request."""
        return self._client._request(method, endpoint, data, params)
    
    async def _async_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an asynchronous API request."""
        return await self._client._async_request(method, endpoint, data, params)
