"""
PayPlus Transactions API.
"""

from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal

from payplus.api.base import BaseAPI


class TransactionsAPI(BaseAPI):
    """
    Transactions API for direct charges and transaction management.
    """
    
    def charge(
        self,
        token: str,
        amount: float | Decimal,
        currency: str = "ILS",
        cvv: Optional[str] = None,
        payments: int = 1,
        description: Optional[str] = None,
        customer_uid: Optional[str] = None,
        more_info: Optional[str] = None,
        more_info_1: Optional[str] = None,
        more_info_2: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Charge a tokenized card directly (J4 transaction).
        
        Args:
            token: Card token
            amount: Amount to charge
            currency: Currency code (default: ILS)
            cvv: CVV if required
            payments: Number of installments
            description: Payment description
            customer_uid: Customer UID
            more_info: Custom field 1
            more_info_1: Custom field 2
            more_info_2: Custom field 3
            
        Returns:
            Transaction result
        """
        data: dict[str, Any] = {
            "card_uid": token,
            "amount": float(amount),
            "currency_code": currency,
            "payments": payments,
        }
        
        if cvv:
            data["card_cvv"] = cvv
        
        if description:
            data["more_info"] = description
        if more_info:
            data["more_info"] = more_info
        if more_info_1:
            data["more_info_1"] = more_info_1
        if more_info_2:
            data["more_info_2"] = more_info_2
        
        if customer_uid:
            data["customer_uid"] = customer_uid
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        for key, value in kwargs.items():
            if key not in data and value is not None:
                data[key] = value
        
        return self._request("POST", "Transactions/Charge", data)
    
    async def async_charge(
        self,
        token: str,
        amount: float | Decimal,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of charge."""
        data: dict[str, Any] = {
            "card_uid": token,
            "amount": float(amount),
            "currency_code": kwargs.get("currency", "ILS"),
            "payments": kwargs.get("payments", 1),
        }
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        return await self._async_request("POST", "Transactions/Charge", data)
    
    def get(self, transaction_uid: str) -> dict[str, Any]:
        """
        Get transaction details.
        
        Args:
            transaction_uid: Transaction UID
            
        Returns:
            Transaction details
        """
        return self._request("GET", f"Transactions/{transaction_uid}")
    
    def refund(
        self,
        transaction_uid: str,
        amount: Optional[float | Decimal] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Refund a transaction.
        
        Args:
            transaction_uid: Transaction UID
            amount: Amount to refund (full refund if not specified)
            
        Returns:
            Refund result
        """
        data: dict[str, Any] = {
            "transaction_uid": transaction_uid,
        }
        
        if amount is not None:
            data["amount"] = float(amount)
        
        return self._request("POST", "Transactions/Refund", data)
    
    def approve(
        self,
        approval_number: str,
        amount: float | Decimal,
        token: str,
        currency: str = "ILS",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Complete a pre-authorized transaction (J5).
        
        Args:
            approval_number: Approval number from authorization
            amount: Amount to capture
            token: Card token
            currency: Currency code
            
        Returns:
            Capture result
        """
        data: dict[str, Any] = {
            "approval_number": approval_number,
            "amount": float(amount),
            "card_uid": token,
            "currency_code": currency,
        }
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        return self._request("POST", "Transactions/Approve", data)
    
    def list(
        self,
        page: int = 1,
        page_size: int = 50,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        List transactions.
        
        Args:
            page: Page number
            page_size: Items per page
            from_date: Start date filter (YYYY-MM-DD)
            to_date: End date filter (YYYY-MM-DD)
            status: Filter by status
            
        Returns:
            List of transactions
        """
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if status:
            params["status"] = status
        
        return self._request("GET", "Transactions", params=params)
