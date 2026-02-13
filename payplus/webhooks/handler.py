"""
Webhook handler for PayPlus IPN (Instant Payment Notification).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional
from enum import Enum

from pydantic import BaseModel, Field

from payplus.exceptions import WebhookError, WebhookSignatureError


class WebhookEventType(str, Enum):
    """PayPlus webhook event types."""
    
    # Payment events
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILURE = "payment.failure"
    PAYMENT_PENDING = "payment.pending"
    
    # Recurring events
    RECURRING_CREATED = "recurring.created"
    RECURRING_CHARGED = "recurring.charged"
    RECURRING_FAILED = "recurring.failed"
    RECURRING_CANCELED = "recurring.canceled"
    
    # Refund events
    REFUND_SUCCESS = "refund.success"
    REFUND_FAILURE = "refund.failure"
    
    # Token events
    TOKEN_CREATED = "token.created"
    
    # Unknown
    UNKNOWN = "unknown"


class WebhookEvent(BaseModel):
    """Parsed webhook event."""
    
    id: str = Field(..., description="Event ID")
    type: WebhookEventType = Field(default=WebhookEventType.UNKNOWN)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # PayPlus specific fields
    transaction_uid: Optional[str] = None
    recurring_uid: Optional[str] = None
    page_request_uid: Optional[str] = None
    approval_number: Optional[str] = None
    
    # Amount
    amount: Optional[float] = None
    currency: Optional[str] = None
    
    # Status
    status: Optional[str] = None
    status_code: Optional[str] = None
    status_description: Optional[str] = None
    
    # Customer
    customer_uid: Optional[str] = None
    customer_email: Optional[str] = None
    
    # Card
    card_uid: Optional[str] = None
    card_brand: Optional[str] = None
    card_last_four: Optional[str] = None
    
    # Custom fields
    more_info: Optional[str] = None
    more_info_1: Optional[str] = None
    more_info_2: Optional[str] = None
    
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
                event = webhook_handler.handle(payload, signature)
                return {"received": True}
            except WebhookSignatureError:
                raise HTTPException(status_code=400, detail="Invalid signature")
    
    Usage with Flask:
        from flask import Flask, request
        from payplus import PayPlus
        from payplus.webhooks import WebhookHandler
        
        app = Flask(__name__)
        client = PayPlus(api_key="...", secret_key="...")
        webhook_handler = WebhookHandler(client)
        
        @app.route("/webhooks/payplus", methods=["POST"])
        def payplus_webhook():
            payload = request.get_data()
            signature = request.headers.get("X-PayPlus-Signature", "")
            
            try:
                event = webhook_handler.handle(payload, signature)
                return {"received": True}, 200
            except WebhookSignatureError:
                return {"error": "Invalid signature"}, 400
    """
    
    def __init__(
        self,
        client: Any,
        verify_signature: bool = True,
    ):
        """
        Initialize webhook handler.
        
        Args:
            client: PayPlus client for signature verification
            verify_signature: Whether to verify webhook signatures
        """
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
        # Verify signature if enabled
        if self.verify_signature and signature:
            if not self.client.verify_webhook_signature(payload, signature):
                raise WebhookSignatureError("Invalid webhook signature")
        
        # Parse payload
        try:
            import json
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise WebhookError(f"Invalid JSON payload: {e}")
        
        # Parse event
        event = self._parse_event(data)
        
        # Call handlers
        self._dispatch(event)
        
        return event
    
    async def handle_async(
        self,
        payload: bytes,
        signature: Optional[str] = None,
    ) -> WebhookEvent:
        """
        Handle an incoming webhook asynchronously.
        
        Same as handle() but calls async handlers.
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
        await self._dispatch_async(event)
        
        return event
    
    def _parse_event(self, data: dict[str, Any]) -> WebhookEvent:
        """Parse raw webhook data into an event."""
        import uuid
        
        # Determine event type based on data
        event_type = self._determine_event_type(data)
        
        # Extract common fields
        results = data.get("results", data.get("data", data))
        
        return WebhookEvent(
            id=data.get("id", str(uuid.uuid4())),
            type=event_type,
            transaction_uid=results.get("transaction_uid"),
            recurring_uid=results.get("recurring_uid"),
            page_request_uid=results.get("page_request_uid"),
            approval_number=results.get("approval_number"),
            amount=results.get("amount"),
            currency=results.get("currency_code"),
            status=results.get("status"),
            status_code=results.get("status_code"),
            status_description=results.get("status_description"),
            customer_uid=results.get("customer", {}).get("customer_uid") if isinstance(results.get("customer"), dict) else results.get("customer_uid"),
            customer_email=results.get("customer", {}).get("email") if isinstance(results.get("customer"), dict) else results.get("customer_email"),
            card_uid=results.get("card_uid"),
            card_brand=results.get("card_brand"),
            card_last_four=results.get("four_digits"),
            more_info=results.get("more_info"),
            more_info_1=results.get("more_info_1"),
            more_info_2=results.get("more_info_2"),
            raw_data=data,
        )
    
    def _determine_event_type(self, data: dict[str, Any]) -> WebhookEventType:
        """Determine the event type from webhook data."""
        results = data.get("results", data.get("data", data))
        status = results.get("status", "").lower()
        
        # Check if it's a recurring payment
        if results.get("recurring_uid"):
            if status == "success" or status == "approved":
                return WebhookEventType.RECURRING_CHARGED
            elif status in ("error", "failed", "declined"):
                return WebhookEventType.RECURRING_FAILED
            elif status == "canceled":
                return WebhookEventType.RECURRING_CANCELED
        
        # Check if it's a regular payment
        if results.get("transaction_uid"):
            if status == "success" or status == "approved":
                return WebhookEventType.PAYMENT_SUCCESS
            elif status in ("error", "failed", "declined"):
                return WebhookEventType.PAYMENT_FAILURE
            elif status == "pending":
                return WebhookEventType.PAYMENT_PENDING
        
        # Check for refund
        if results.get("refund_uid") or "refund" in str(data).lower():
            if status == "success" or status == "approved":
                return WebhookEventType.REFUND_SUCCESS
            else:
                return WebhookEventType.REFUND_FAILURE
        
        # Check for token creation
        if results.get("card_uid") and not results.get("transaction_uid"):
            return WebhookEventType.TOKEN_CREATED
        
        return WebhookEventType.UNKNOWN
    
    def _dispatch(self, event: WebhookEvent) -> None:
        """Dispatch event to registered handlers."""
        handlers = self._handlers.get(event.type.value, [])
        handlers.extend(self._handlers.get("*", []))  # Catch-all handlers
        
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # Log error but continue with other handlers
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
        from fastapi import APIRouter, Request, HTTPException
    except ImportError:
        raise ImportError("FastAPI is required. Install with: pip install payplus-sdk[fastapi]")
    
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
