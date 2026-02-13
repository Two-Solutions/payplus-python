"""
PayPlus SDK Exceptions.
"""

from typing import Any, Optional


class PayPlusError(Exception):
    """Base exception for PayPlus SDK."""
    pass


class PayPlusAPIError(PayPlusError):
    """Exception raised for API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response or {}
    
    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class PayPlusAuthError(PayPlusAPIError):
    """Exception raised for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class PayPlusValidationError(PayPlusError):
    """Exception raised for validation errors."""
    pass


class SubscriptionError(PayPlusError):
    """Exception raised for subscription-related errors."""
    pass


class WebhookError(PayPlusError):
    """Exception raised for webhook-related errors."""
    pass


class WebhookSignatureError(WebhookError):
    """Exception raised when webhook signature verification fails."""
    pass
