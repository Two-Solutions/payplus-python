"""
PayPlus API Client - Core HTTP client for PayPlus payment gateway.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional

import httpx

from payplus.api.payments import PaymentsAPI
from payplus.api.recurring import RecurringAPI
from payplus.api.transactions import TransactionsAPI
from payplus.api.payment_pages import PaymentPagesAPI
from payplus.exceptions import PayPlusError, PayPlusAPIError, PayPlusAuthError


class PayPlus:
    """
    PayPlus API client.
    
    Usage:
        client = PayPlus(
            api_key="your_api_key",
            secret_key="your_secret_key",
            terminal_uid="your_terminal_uid"
        )
        
        # Generate a payment link
        link = client.payment_pages.generate_link(
            amount=100.00,
            currency="ILS",
            description="Monthly subscription"
        )
    """
    
    BASE_URL = "https://restapi.payplus.co.il/api/v1.0"
    SANDBOX_URL = "https://restapidev.payplus.co.il/api/v1.0"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        terminal_uid: Optional[str] = None,
        sandbox: bool = False,
        timeout: float = 30.0,
    ):
        """
        Initialize PayPlus client.
        
        Args:
            api_key: PayPlus API key
            secret_key: PayPlus secret key
            terminal_uid: Terminal UID (optional, uses default if not provided)
            sandbox: Use sandbox environment
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.terminal_uid = terminal_uid
        self.sandbox = sandbox
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        
        self._client = httpx.Client(
            timeout=timeout,
            headers=self._get_headers(),
        )
        
        self._async_client: Optional[httpx.AsyncClient] = None
        
        # API endpoints
        self.payments = PaymentsAPI(self)
        self.recurring = RecurringAPI(self)
        self.transactions = TransactionsAPI(self)
        self.payment_pages = PaymentPagesAPI(self)
    
    def _get_headers(self) -> dict[str, str]:
        """Get default headers for API requests."""
        return {
            "Content-Type": "application/json",
            "Authorization": json.dumps({
                "api_key": self.api_key,
                "secret_key": self.secret_key,
            }),
        }
    
    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=30.0,
                headers=self._get_headers(),
            )
        return self._async_client
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a synchronous API request."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self._client.request(
                method=method,
                url=url,
                json=data,
                params=params,
            )
            return self._handle_response(response)
        except httpx.HTTPError as e:
            raise PayPlusError(f"HTTP error: {e}") from e
    
    async def _async_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an asynchronous API request."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = await self.async_client.request(
                method=method,
                url=url,
                json=data,
                params=params,
            )
            return self._handle_response(response)
        except httpx.HTTPError as e:
            raise PayPlusError(f"HTTP error: {e}") from e
    
    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response."""
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise PayPlusError(f"Invalid JSON response: {response.text}")
        
        if response.status_code == 401:
            raise PayPlusAuthError("Authentication failed. Check your API credentials.")
        
        if response.status_code >= 400:
            error_msg = data.get("message") or data.get("error") or str(data)
            raise PayPlusAPIError(
                message=error_msg,
                status_code=response.status_code,
                response=data,
            )
        
        # PayPlus specific error handling
        if isinstance(data, dict):
            results = data.get("results", {})
            if isinstance(results, dict) and results.get("status") == "error":
                raise PayPlusAPIError(
                    message=results.get("description", "Unknown error"),
                    status_code=response.status_code,
                    response=data,
                )
        
        return data
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """
        Verify webhook/IPN signature.
        
        Args:
            payload: Raw request body
            signature: Signature from X-PayPlus-Signature header
            
        Returns:
            True if signature is valid
        """
        expected = hmac.new(
            self.secret_key.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def close(self) -> None:
        """Close HTTP clients."""
        self._client.close()
        if self._async_client:
            # Note: for async client, use await client.aclose() in async context
            pass
    
    async def aclose(self) -> None:
        """Close async HTTP client."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
    
    def __enter__(self) -> "PayPlus":
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()
