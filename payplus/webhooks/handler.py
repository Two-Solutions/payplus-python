"""
Webhook handler for PayPlus IPN (Instant Payment Notification).

PayPlus callback payload structure:
{
    "transaction_type": "Charge",
    "transaction": {
        "uid": "...",
        "payment_request_uid": "...",
        "status_code": "000",
        "amount": 100,
        "currency": "ILS",
        "approval_number": "...",
        "more_info": "...",
        "recurring_charge_information": {
            "recurring_uid": "...",
            "charge_uid": "..."
        }
    },
    "data": {
        "customer_uid": "...",
        "card_information": {
            "four_digits": "1234",
            "card_holder_name": "...",
            "expiry_month": "09",
            "expiry_year": "24",
            "brand_id": 8
        }
    },
    "invoice": { ... }
}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from payplus.exceptions import WebhookError, WebhookSignatureError


class WebhookEventType(str, Enum):
    """PayPlus webhook event types."""

    # Payment events
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILURE = "payment.failure"

    # Recurring events
    RECURRING_CHARGED = "recurring.charged"
    RECURRING_FAILED = "recurring.failed"
    RECURRING_CANCELED = "recurring.canceled"

    # Refund events
    REFUND_SUCCESS = "refund.success"

    # Unknown
    UNKNOWN = "unknown"


class WebhookEvent(BaseModel):
    """Parsed webhook event."""

    id: str = Field(..., description="Event ID")
    type: WebhookEventType = Field(default=WebhookEventType.UNKNOWN)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Transaction
    transaction_uid: Optional[str] = None
    transaction_type: Optional[str] = None
    status_code: Optional[str] = None
    approval_number: Optional[str] = None

    # Payment page
    page_request_uid: Optional[str] = None

    # Recurring
    recurring_uid: Optional[str] = None
    charge_uid: Optional[str] = None

    # Amount
    amount: Optional[float] = None
    currency: Optional[str] = None

    # Customer
    customer_uid: Optional[str] = None

    # Card
    card_four_digits: Optional[str] = None
    card_holder_name: Optional[str] = None
    card_expiry_month: Optional[str] = None
    card_expiry_year: Optional[str] = None
    card_brand_id: Optional[int] = None

    # Custom fields
    more_info: Optional[str] = None
    more_info_1: Optional[str] = None
    more_info_2: Optional[str] = None
    more_info_3: Optional[str] = None
    more_info_4: Optional[str] = None
    more_info_5: Optional[str] = None

    # Raw data
    raw_data: dict[str, Any] = Field(default_factory=dict)


class WebhookHandler:
    """
    Handler for PayPlus IPN (webhook) notifications.

    Usage with FastAPI:
        from fastapi import FastAPI, Request, HTTPException
        from payplus import PayPlus
        from payplus.webhooks import WebhookHandler

        app = FastAPI()
        client = PayPlus(api_key="...", secret_key="...")
        webhook_handler = WebhookHandler(client)

        @webhook_handler.on("payment.success")
        async def handle_payment_success(event: WebhookEvent):
            print(f"Payment succeeded: {event.transaction_uid}")

        @app.post("/webhooks/payplus")
        async def payplus_webhook(request: Request):
            payload = await request.body()
            signature = request.headers.get("X-PayPlus-Signature", "")

            try:
                event = await webhook_handler.handle_async(payload, signature)
                return {"received": True}
            except WebhookSignatureError:
                raise HTTPException(status_code=400, detail="Invalid signature")
    """

    def __init__(
        self,
        client: Any,
        verify_signature: bool = True,
    ):
        self.client = client
        self.verify_signature = verify_signature
        self._handlers: dict[str, list[Callable[[WebhookEvent], Any]]] = {}

    def on(self, event_type: str) -> Callable:
        """
        Decorator to register an event handler.

        Args:
            event_type: Event type to handle (e.g., "payment.success")
        """
        def decorator(func: Callable[[WebhookEvent], Any]) -> Callable:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            return func
        return decorator

    def register_handler(
        self,
        event_type: str,
        handler: Callable[[WebhookEvent], Any],
    ) -> None:
        """Register an event handler programmatically."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def handle(
        self,
        payload: bytes,
        signature: Optional[str] = None,
    ) -> WebhookEvent:
        """
        Handle an incoming webhook.

        Args:
            payload: Raw request body
            signature: Signature from X-PayPlus-Signature header

        Returns:
            Parsed webhook event

        Raises:
            WebhookSignatureError: If signature verification fails
            WebhookError: If payload parsing fails
        """
        if self.verify_signature and signature:
            if not self.client.verify_webhook_signature(payload, signature):
                raise WebhookSignatureError("Invalid webhook signature")

        try:
            import json
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise WebhookError(f"Invalid JSON payload: {e}")

        event = self._parse_event(data)
        self._dispatch(event)
        return event

    async def handle_async(
        self,
        payload: bytes,
        signature: Optional[str] = None,
    ) -> WebhookEvent:
        """Handle an incoming webhook asynchronously."""
        if self.verify_signature and signature:
            if not self.client.verify_webhook_signature(payload, signature):
                raise WebhookSignatureError("Invalid webhook signature")

        try:
            import json
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise WebhookError(f"Invalid JSON payload: {e}")

        event = self._parse_event(data)
        await self._dispatch_async(event)
        return event

    def _parse_event(self, data: dict[str, Any]) -> WebhookEvent:
        """
        Parse raw webhook data into an event.

        Handles the PayPlus callback structure:
            transaction_type, transaction.*, data.*, invoice.*
        """
        transaction = data.get("transaction", {})
        payload_data = data.get("data", {})
        card_info = payload_data.get("card_information", {})
        recurring_info = transaction.get("recurring_charge_information", {})

        event_type = self._determine_event_type(data)

        return WebhookEvent(
            id=transaction.get("uid", str(uuid.uuid4())),
            type=event_type,
            transaction_uid=transaction.get("uid"),
            transaction_type=data.get("transaction_type"),
            status_code=transaction.get("status_code"),
            approval_number=transaction.get("approval_number"),
            page_request_uid=transaction.get("payment_request_uid"),
            recurring_uid=recurring_info.get("recurring_uid"),
            charge_uid=recurring_info.get("charge_uid"),
            amount=transaction.get("amount"),
            currency=transaction.get("currency"),
            customer_uid=payload_data.get("customer_uid"),
            card_four_digits=card_info.get("four_digits"),
            card_holder_name=card_info.get("card_holder_name"),
            card_expiry_month=card_info.get("expiry_month"),
            card_expiry_year=card_info.get("expiry_year"),
            card_brand_id=card_info.get("brand_id"),
            more_info=transaction.get("more_info"),
            more_info_1=transaction.get("more_info_1"),
            more_info_2=transaction.get("more_info_2"),
            more_info_3=transaction.get("more_info_3"),
            more_info_4=transaction.get("more_info_4"),
            more_info_5=transaction.get("more_info_5"),
            raw_data=data,
        )

    def _determine_event_type(self, data: dict[str, Any]) -> WebhookEventType:
        """Determine the event type from webhook data."""
        transaction = data.get("transaction", {})
        transaction_type = data.get("transaction_type", "").lower()
        status_code = transaction.get("status_code", "")
        recurring_info = transaction.get("recurring_charge_information", {})
        has_recurring = bool(recurring_info.get("recurring_uid"))

        # status_code "000" means success
        is_success = status_code == "000"

        # Refund
        if transaction_type == "refund":
            return WebhookEventType.REFUND_SUCCESS if is_success else WebhookEventType.UNKNOWN

        # Recurring charge (has recurring_charge_information)
        if has_recurring:
            if is_success:
                return WebhookEventType.RECURRING_CHARGED
            return WebhookEventType.RECURRING_FAILED

        # Regular payment
        if transaction.get("uid"):
            if is_success:
                return WebhookEventType.PAYMENT_SUCCESS
            return WebhookEventType.PAYMENT_FAILURE

        return WebhookEventType.UNKNOWN

    def _dispatch(self, event: WebhookEvent) -> None:
        """Dispatch event to registered handlers."""
        handlers = self._handlers.get(event.type.value, [])
        handlers.extend(self._handlers.get("*", []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass

    async def _dispatch_async(self, event: WebhookEvent) -> None:
        """Dispatch event to registered async handlers."""
        import asyncio

        handlers = self._handlers.get(event.type.value, [])
        handlers.extend(self._handlers.get("*", []))

        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass


def create_fastapi_webhook_router(
    handler: WebhookHandler,
    path: str = "/webhooks/payplus",
) -> Any:
    """
    Create a FastAPI router for webhooks.

    Usage:
        from fastapi import FastAPI
        from payplus import PayPlus
        from payplus.webhooks import WebhookHandler, create_fastapi_webhook_router

        app = FastAPI()
        client = PayPlus(...)
        handler = WebhookHandler(client)

        router = create_fastapi_webhook_router(handler)
        app.include_router(router)
    """
    try:
        from fastapi import APIRouter, HTTPException, Request
    except ImportError:
        raise ImportError("FastAPI is required. Install with: pip install payplus-python[fastapi]")

    router = APIRouter()

    @router.post(path)
    async def webhook_endpoint(request: Request):
        payload = await request.body()
        signature = request.headers.get("X-PayPlus-Signature", "")

        try:
            event = await handler.handle_async(payload, signature)
            return {"received": True, "event_id": event.id, "event_type": event.type.value}
        except WebhookSignatureError:
            raise HTTPException(status_code=400, detail="Invalid signature")
        except WebhookError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router
