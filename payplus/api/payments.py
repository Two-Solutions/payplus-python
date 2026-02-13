"""
PayPlus Payments API - General payment utilities.
"""

from __future__ import annotations

from typing import Any, Optional

from payplus.api.base import BaseAPI


class PaymentsAPI(BaseAPI):
    """
    General Payments API utilities.
    """
    
    def check_card(
        self,
        card_number: str,
        expiry_month: str,
        expiry_year: str,
        cvv: Optional[str] = None,
        holder_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Validate a card without charging it.
        
        Args:
            card_number: Card number
            expiry_month: Expiration month (MM)
            expiry_year: Expiration year (YY or YYYY)
            cvv: CVV (optional)
            holder_id: Card holder ID
            
        Returns:
            Card validation result
        """
        data: dict[str, Any] = {
            "credit_card_number": card_number,
            "card_date_mmyy": f"{expiry_month}{expiry_year[-2:]}",
        }
        
        if cvv:
            data["card_cvv"] = cvv
        if holder_id:
            data["holder_id"] = holder_id
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        return self._request("POST", "Payments/CheckCard", data)
    
    def tokenize(
        self,
        card_number: str,
        expiry_month: str,
        expiry_year: str,
        cvv: Optional[str] = None,
        holder_name: Optional[str] = None,
        holder_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Tokenize a card for future charges.
        
        Args:
            card_number: Card number
            expiry_month: Expiration month (MM)
            expiry_year: Expiration year (YY or YYYY)
            cvv: CVV
            holder_name: Card holder name
            holder_id: Card holder ID
            
        Returns:
            Tokenization result with card_uid
        """
        data: dict[str, Any] = {
            "credit_card_number": card_number,
            "card_date_mmyy": f"{expiry_month}{expiry_year[-2:]}",
        }
        
        if cvv:
            data["card_cvv"] = cvv
        if holder_name:
            data["card_holder_name"] = holder_name
        if holder_id:
            data["holder_id"] = holder_id
        
        if self._client.terminal_uid:
            data["terminal_uid"] = self._client.terminal_uid
        
        return self._request("POST", "Payments/Tokenize", data)
    
    def get_token(self, token_uid: str) -> dict[str, Any]:
        """
        Get tokenized card details.
        
        Args:
            token_uid: Card token UID
            
        Returns:
            Token details (masked card info)
        """
        return self._request("GET", f"Payments/Token/{token_uid}")
    
    def delete_token(self, token_uid: str) -> dict[str, Any]:
        """
        Delete a card token.
        
        Args:
            token_uid: Card token UID
            
        Returns:
            Deletion result
        """
        return self._request("DELETE", f"Payments/Token/{token_uid}")
