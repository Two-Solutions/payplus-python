"""
PayPlus Customers API.
"""

from __future__ import annotations

from typing import Any, Optional

from payplus.api.base import BaseAPI


class CustomersAPI(BaseAPI):
    """
    Customers API for creating and managing customers on PayPlus.
    """

    def add(
        self,
        customer_name: str,
        email: str,
        phone: Optional[str] = None,
        vat_number: Optional[int] = None,
        paying_vat: bool = True,
        customer_number: Optional[str] = None,
        notes: Optional[str] = None,
        contacts: Optional[list[dict[str, Any]]] = None,
        business_address: Optional[str] = None,
        business_city: Optional[str] = None,
        business_postal_code: Optional[str] = None,
        business_country_iso: str = "IL",
        subject_code: Optional[str] = None,
        communication_email: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create a new customer on PayPlus.

        Args:
            customer_name: Customer name (required)
            email: Customer email (required)
            phone: Customer phone number
            vat_number: Customer or company VAT number
            paying_vat: Whether customer pays VAT
            customer_number: Internal customer number
            notes: Notes about the customer
            contacts: List of contact dicts
            business_address: Business address
            business_city: Business city
            business_postal_code: Business postal code
            business_country_iso: Business country code (default: IL)
            subject_code: External customer number from ERP
            communication_email: Email for communication

        Returns:
            API response with customer_uid in data
        """
        data: dict[str, Any] = {
            "customer_name": customer_name,
            "email": email,
            "paying_vat": paying_vat,
        }

        if phone is not None:
            data["phone"] = phone
        if vat_number is not None:
            data["vat_number"] = vat_number
        if customer_number is not None:
            data["customer_number"] = customer_number
        if notes is not None:
            data["notes"] = notes
        if contacts is not None:
            data["contacts"] = contacts
        if business_address is not None:
            data["business_address"] = business_address
        if business_city is not None:
            data["business_city"] = business_city
        if business_postal_code is not None:
            data["business_postal_code"] = business_postal_code
        if business_country_iso != "IL":
            data["business_country_iso"] = business_country_iso
        if subject_code is not None:
            data["subject_code"] = subject_code
        if communication_email is not None:
            data["communication_email"] = communication_email

        for key, value in kwargs.items():
            if key not in data and value is not None:
                data[key] = value

        return self._request("POST", "Customers/Add", data)

    async def async_add(
        self,
        customer_name: str,
        email: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of add."""
        data: dict[str, Any] = {
            "customer_name": customer_name,
            "email": email,
            "paying_vat": kwargs.pop("paying_vat", True),
        }

        if kwargs.get("phone") is not None:
            data["phone"] = kwargs.pop("phone")
        if kwargs.get("vat_number") is not None:
            data["vat_number"] = kwargs.pop("vat_number")

        for key, value in kwargs.items():
            if key not in data and value is not None:
                data[key] = value

        return await self._async_request("POST", "Customers/Add", data)
