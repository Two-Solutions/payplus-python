"""
PayPlus Recurring Payments API.
"""

from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal
from datetime import date, datetime

from payplus.api.base import BaseAPI


class RecurringAPI(BaseAPI):
    """
    Recurring Payments API for creating and managing recurring charges.
    """
    
    def add(
        self,
        token: str,
        amount: float | Decimal,
        currency: str = "ILS",
        description: Optional[str] = None,
        start_date: Optional[date | datetime | str] = None,
        end_date: Optional[date | datetime | str] = None,
        interval: str = "month",
        interval_count: int = 1,
        initial_amount: Optional[float | Decimal] = None,
        customer_uid: Optional[str] = None,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        payments: int = 1,
        more_info: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create a recurring payment.
        
        Args:
            token: Card token from initial payment
            amount: Recurring amount
            currency: Currency code (default: ILS)
            description: Payment description
            start_date: When to start the recurring
            end_date: When to end the recurring
            interval: Billing interval (day/week/month/year)
            interval_count: Number of intervals between charges
            initial_amount: Initial charge amount (if different)
            customer_uid: Customer UID
            customer_email: Customer email
            customer_name: Customer name
            payments: Number of installments per charge
            more_info: Custom field
            
        Returns:
            API response with recurring payment details
        """
        data: dict[str, Any] = {
            "card_uid": token,
            "amount": float(amount),
            "currency_code": currency,
            "recurring_type": self._get_recurring_type(interval),
            "recurring_amount": interval_count,
            "payments": payments,
        }
        
        if description:
            data["more_info"] = description
        if more_info:
            data["more_info"] = more_info
        
        if start_date:
            data["start_date"] = self._format_date(start_date)
        if end_date:
            data["end_date"] = self._format_date(end_date)
        
        if initial_amount is not None:
            data["initial_amount"] = float(initial_amount)
        
        # Customer info
        customer = {}
        if customer_uid:
            customer["customer_uid"] = customer_uid
        if customer_email:
            customer["email"] = customer_email
        if customer_name:
            customer["customer_name"] = customer_name
        if customer:
            data["customer"] = customer
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        for key, value in kwargs.items():
            if key not in data and value is not None:
                data[key] = value
        
        return self._request("POST", "RecurringPayments/Add", data)
    
    async def async_add(
        self,
        token: str,
        amount: float | Decimal,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of add."""
        data: dict[str, Any] = {
            "card_uid": token,
            "amount": float(amount),
            "currency_code": kwargs.get("currency", "ILS"),
            "recurring_type": self._get_recurring_type(kwargs.get("interval", "month")),
            "recurring_amount": kwargs.get("interval_count", 1),
            "payments": kwargs.get("payments", 1),
        }
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        return await self._async_request("POST", "RecurringPayments/Add", data)
    
    def charge(
        self,
        recurring_uid: str,
        amount: Optional[float | Decimal] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Manually charge a recurring payment.
        
        Args:
            recurring_uid: Recurring payment UID
            amount: Amount to charge (uses default if not specified)
            
        Returns:
            Charge result
        """
        data: dict[str, Any] = {
            "recurring_uid": recurring_uid,
        }
        
        if amount is not None:
            data["amount"] = float(amount)
        
        return self._request("POST", "RecurringPayments/Charge", data)
    
    def update(
        self,
        recurring_uid: str,
        customer_uid: str,
        card_token: str,
        currency_code: str = "ILS",
        recurring_type: int = 2,
        recurring_range: int = 1,
        number_of_charges: int = 0,
        start_date: Optional[date | datetime | str] = None,
        end_date: Optional[date | datetime | str] = None,
        instant_first_payment: bool = False,
        items: Optional[list[dict[str, Any]]] = None,
        one_time_items: Optional[list[dict[str, Any]]] = None,
        one_time_charge_date: Optional[str] = None,
        successful_invoice: bool = False,
        send_customer_success_email: bool = False,
        customer_failure_email: bool = False,
        extra_info: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Update an existing recurring payment.

        Args:
            recurring_uid: Recurring payment UID
            customer_uid: Customer UID on PayPlus
            card_token: Saved card UID
            currency_code: Currency (ILS, USD, EUR, GPB)
            recurring_type: 0=Daily, 1=Weekly, 2=Monthly
            recurring_range: Frequency multiplier (e.g. 2 = every 2 months)
            number_of_charges: Total charges (0 = unlimited)
            start_date: Next charge date (can't be today)
            end_date: When recurring stops (for unlimited)
            instant_first_payment: Charge immediately
            items: Recurring line items (product_uid, quantity, price)
            one_time_items: One-time charge items
            one_time_charge_date: When to process one-time charge
            successful_invoice: Create invoice on successful charge
            send_customer_success_email: Email customer on success
            customer_failure_email: Email customer on failure
            extra_info: Additional info

        Returns:
            API response with recurring_payment_uid
        """
        data: dict[str, Any] = {
            "customer_uid": customer_uid,
            "card_token": card_token,
            "currency_code": currency_code,
            "recurring_type": recurring_type,
            "recurring_range": recurring_range,
            "number_of_charges": number_of_charges,
            "instant_first_payment": instant_first_payment,
            "successful_invoice": successful_invoice,
            "send_customer_success_email": send_customer_success_email,
            "customer_failure_email": customer_failure_email,
        }

        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid

        if start_date:
            data["start_date"] = self._format_date(start_date)
        if end_date:
            data["end_date"] = self._format_date(end_date)
        if items is not None:
            data["items"] = items
        if one_time_items is not None:
            data["one_time_items"] = one_time_items
        if one_time_charge_date is not None:
            data["one_time_charge_date"] = one_time_charge_date
        if extra_info is not None:
            data["extra_info"] = extra_info

        for key, value in kwargs.items():
            if key not in data and value is not None:
                data[key] = value

        return self._request(
            "POST", f"RecurringPayments/Update/{recurring_uid}", data
        )

    def cancel(self, recurring_uid: str) -> dict[str, Any]:
        """
        Cancel a recurring payment.
        
        Args:
            recurring_uid: Recurring payment UID
            
        Returns:
            Cancellation result
        """
        return self._request("POST", "RecurringPayments/Cancel", {
            "recurring_uid": recurring_uid,
        })
    
    def get(self, recurring_uid: str) -> dict[str, Any]:
        """
        Get recurring payment details.
        
        Args:
            recurring_uid: Recurring payment UID
            
        Returns:
            Recurring payment details
        """
        return self._request("GET", f"RecurringPayments/{recurring_uid}")
    
    def list(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        List recurring payments.
        
        Args:
            page: Page number
            page_size: Items per page
            status: Filter by status
            
        Returns:
            List of recurring payments
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        
        return self._request("GET", "RecurringPayments", params=params)
    
    def _get_recurring_type(self, interval: str) -> int:
        """Convert interval string to PayPlus recurring type."""
        mapping = {
            "day": 1,
            "week": 2,
            "month": 3,
            "year": 4,
        }
        return mapping.get(interval.lower(), 3)  # Default to monthly
    
    def _format_date(self, d: date | datetime | str) -> str:
        """Format date for PayPlus API."""
        if isinstance(d, str):
            return d
        if isinstance(d, datetime):
            return d.strftime("%Y-%m-%d")
        return d.strftime("%Y-%m-%d")
