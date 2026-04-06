"""
PayPlus Payment Pages API.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from payplus.api.base import BaseAPI


def build_recurring_settings(
    billing_cycle: str,
    trial_days: int = 0,
    number_of_charges: int = 0,
    instant_first_payment: bool = True,
    start_date_on_payment_date: bool = True,
    start_date: int = 1,
    successful_invoice: bool = True,
    customer_failure_email: bool = True,
    send_customer_success_email: bool = True,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build recurring_settings dict from a billing cycle and options.

    Args:
        billing_cycle: One of "daily", "weekly", "monthly", "quarterly", "yearly"
        trial_days: Free days before first charge (maps to jump_payments)
        number_of_charges: Total charges (0 = unlimited)
        instant_first_payment: Charge immediately on first payment
        start_date_on_payment_date: Start recurring on payment date
        start_date: Day of month for recurring (1-28), used when start_date_on_payment_date=False
        successful_invoice: Create invoice for each successful payment
        customer_failure_email: Email customer on failed payment
        send_customer_success_email: Email customer on successful charge
        end_date: When the recurring will stop (for unlimited recurring)

    Returns:
        Dict matching PayPlus recurring_settings schema

    Mapping:
        DAILY     -> recurring_type=0, recurring_range=1
        WEEKLY    -> recurring_type=1, recurring_range=1
        MONTHLY   -> recurring_type=2, recurring_range=1
        QUARTERLY -> recurring_type=2, recurring_range=3
        YEARLY    -> recurring_type=2, recurring_range=12
    """
    cycle_map: dict[str, tuple[int, int]] = {
        "daily": (0, 1),
        "weekly": (1, 1),
        "monthly": (2, 1),
        "quarterly": (2, 3),
        "yearly": (2, 12),
    }

    recurring_type, recurring_range = cycle_map.get(billing_cycle, (2, 1))

    settings: dict[str, Any] = {
        "recurring_type": recurring_type,
        "recurring_range": recurring_range,
        "number_of_charges": number_of_charges,
        "instant_first_payment": instant_first_payment,
        "start_date_on_payment_date": start_date_on_payment_date,
        "start_date": start_date,
        "jump_payments": trial_days,
        "successful_invoice": successful_invoice,
        "customer_failure_email": customer_failure_email,
        "send_customer_success_email": send_customer_success_email,
    }

    if end_date is not None:
        settings["end_date"] = end_date

    return settings


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
        language: str = "he",
        expiration_time: int = 60,
        more_info: Optional[str] = None,
        more_info_2: Optional[str] = None,
        more_info_3: Optional[str] = None,
        more_info_4: Optional[str] = None,
        more_info_5: Optional[str] = None,
        items: Optional[list[dict[str, Any]]] = None,
        recurring_settings: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate a payment link for hosted checkout.

        Args:
            amount: Payment amount
            currency: Currency code (default: ILS)
            description: Payment description
            customer_uid: Existing PayPlus customer UID
            customer_email: Customer email
            customer_name: Customer name
            customer_phone: Customer phone
            charge_method: 0=Check, 1=Charge, 2=Approval, 3=Recurring, 4=Refund, 5=Token
            payments: Number of installments
            min_payments: Minimum installments
            max_payments: Maximum installments
            success_url: URL to redirect on success
            failure_url: URL to redirect on failure
            cancel_url: URL to redirect on cancel
            callback_url: IPN/webhook callback URL
            create_token: Whether to tokenize the card
            language: Page language (he/en)
            expiration_time: Link expiration in minutes
            more_info: Custom field 1
            more_info_2: Custom field 2
            more_info_3: Custom field 3
            more_info_4: Custom field 4
            more_info_5: Custom field 5
            items: List of items with name, price, quantity
            recurring_settings: Recurring payment settings (use build_recurring_settings helper)

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
            "expiry_datetime": str(expiration_time),
        }

        if description:
            data["more_info"] = description
        if more_info:
            data["more_info"] = more_info
        if more_info_2:
            data["more_info_2"] = more_info_2
        if more_info_3:
            data["more_info_3"] = more_info_3
        if more_info_4:
            data["more_info_4"] = more_info_4
        if more_info_5:
            data["more_info_5"] = more_info_5

        # Customer info
        customer: dict[str, str] = {}
        if customer_uid:
            customer["uid"] = customer_uid
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
            data["refURL_success"] = success_url
        if failure_url:
            data["refURL_failure"] = failure_url
        if cancel_url:
            data["refURL_cancel"] = cancel_url
        if callback_url:
            data["refURL_callback"] = callback_url

        # Items
        if items:
            data["items"] = items

        # Recurring settings
        if recurring_settings:
            data["recurring_settings"] = recurring_settings

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
        currency: str = "ILS",
        description: Optional[str] = None,
        customer_uid: Optional[str] = None,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        charge_method: int = 1,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        create_token: bool = False,
        language: str = "he",
        items: Optional[list[dict[str, Any]]] = None,
        recurring_settings: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of generate_link."""
        data: dict[str, Any] = {
            "charge_method": charge_method,
            "amount": float(amount),
            "currency_code": currency,
            "sendEmailApproval": kwargs.get("send_email_approval", True),
            "sendEmailFailure": kwargs.get("send_email_failure", False),
            "create_token": create_token,
            "language_code": language,
        }

        if kwargs.get("payment_page_uid"):
            data["payment_page_uid"] = kwargs["payment_page_uid"]

        if description:
            data["more_info"] = description

        # Customer info
        customer: dict[str, str] = {}
        if customer_uid:
            customer["uid"] = customer_uid
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
            data["refURL_success"] = success_url
        if failure_url:
            data["refURL_failure"] = failure_url
        if cancel_url:
            data["refURL_cancel"] = cancel_url
        if callback_url:
            data["refURL_callback"] = callback_url

        # Items
        if items:
            data["items"] = items

        # Recurring settings
        if recurring_settings:
            data["recurring_settings"] = recurring_settings

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
