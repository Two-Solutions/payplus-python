"""
PayPlus Payment Pages API.
"""

from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal

from payplus.api.base import BaseAPI


class PaymentPagesAPI(BaseAPI):
    """
    Payment Pages API for generating payment links and handling hosted checkout.
    """
    
    def generate_link(
        self,
        amount: float | Decimal,
        currency: str = "ILS",
        description: Optional[str] = None,
        customer_uid: Optional[str] = None,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        charge_method: int = 1,
        payments: int = 1,
        min_payments: int = 1,
        max_payments: int = 12,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        create_token: bool = False,
        refurl_address: Optional[str] = None,
        language: str = "he",
        expiration_time: int = 60,
        more_info: Optional[str] = None,
        more_info_1: Optional[str] = None,
        more_info_2: Optional[str] = None,
        items: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate a payment link for hosted checkout.
        
        Args:
            amount: Payment amount
            currency: Currency code (default: ILS)
            description: Payment description
            customer_uid: Existing customer UID
            customer_email: Customer email
            customer_name: Customer name
            customer_phone: Customer phone
            charge_method: Charge method (1=regular, 2=recurring, 3=token only)
            payments: Number of installments
            min_payments: Minimum installments
            max_payments: Maximum installments
            success_url: URL to redirect on success
            failure_url: URL to redirect on failure
            cancel_url: URL to redirect on cancel
            callback_url: IPN/webhook callback URL
            create_token: Whether to tokenize the card
            refurl_address: Refund URL
            language: Page language (he/en)
            expiration_time: Link expiration in minutes
            more_info: Custom field 1
            more_info_1: Custom field 2
            more_info_2: Custom field 3
            items: List of items with name, price, quantity
            
        Returns:
            API response with payment link URL
        """
        data: dict[str, Any] = {
            "payment_page_uid": kwargs.get("payment_page_uid"),
            "charge_method": charge_method,
            "amount": float(amount),
            "currency_code": currency,
            "sendEmailApproval": kwargs.get("send_email_approval", True),
            "sendEmailFailure": kwargs.get("send_email_failure", False),
            "create_token": create_token,
            "payments": payments,
            "min_payments": min_payments,
            "max_payments": max_payments,
            "language_code": language,
            "expiry_datetime": expiration_time,
        }
        
        if description:
            data["more_info"] = description
        if more_info:
            data["more_info"] = more_info
        if more_info_1:
            data["more_info_1"] = more_info_1
        if more_info_2:
            data["more_info_2"] = more_info_2
        
        # Customer info
        customer = {}
        if customer_uid:
            customer["customer_uid"] = customer_uid
        if customer_email:
            customer["email"] = customer_email
        if customer_name:
            customer["customer_name"] = customer_name
        if customer_phone:
            customer["phone"] = customer_phone
        if customer:
            data["customer"] = customer
        
        # URLs
        if success_url:
            data["success_page_url"] = success_url
        if failure_url:
            data["failure_page_url"] = failure_url
        if cancel_url:
            data["cancel_page_url"] = cancel_url
        if callback_url:
            data["callback_url"] = callback_url
        if refurl_address:
            data["refurl_address"] = refurl_address
        
        # Items
        if items:
            data["items"] = items
        
        # Add terminal if set
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        # Add any extra kwargs
        for key, value in kwargs.items():
            if key not in data and value is not None:
                data[key] = value
        
        return self._request("POST", "PaymentPages/generateLink", data)
    
    async def async_generate_link(
        self,
        amount: float | Decimal,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of generate_link."""
        # Build data same as sync version
        data: dict[str, Any] = {
            "charge_method": kwargs.get("charge_method", 1),
            "amount": float(amount),
            "currency_code": kwargs.get("currency", "ILS"),
            "sendEmailApproval": kwargs.get("send_email_approval", True),
            "sendEmailFailure": kwargs.get("send_email_failure", False),
            "create_token": kwargs.get("create_token", False),
            "payments": kwargs.get("payments", 1),
            "language_code": kwargs.get("language", "he"),
        }
        
        if kwargs.get("description"):
            data["more_info"] = kwargs["description"]
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        return await self._async_request("POST", "PaymentPages/generateLink", data)
    
    def get_status(self, page_request_uid: str) -> dict[str, Any]:
        """
        Get payment page status.
        
        Args:
            page_request_uid: Payment page request UID
            
        Returns:
            Payment page status
        """
        return self._request("GET", f"PaymentPages/{page_request_uid}")
