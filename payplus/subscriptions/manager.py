"""
Subscription Manager - Orchestration layer for subscription management via PayPlus payment links.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Optional

from payplus.api.payment_pages import build_recurring_settings
from payplus.exceptions import PayPlusError, SubscriptionError
from payplus.models.customer import Customer
from payplus.models.subscription import BillingCycle, Subscription, SubscriptionStatus
from payplus.models.tier import Tier

if TYPE_CHECKING:
    from payplus.client import PayPlus
    from payplus.subscriptions.storage import StorageBackend
    from payplus.webhooks.handler import WebhookEvent


class SubscriptionManager:
    """
    High-level subscription management for SaaS applications.

    Creates subscriptions by generating PayPlus payment links with recurring settings.
    When the customer pays, PayPlus handles recurring billing automatically.
    Webhook events update subscription state.

    Usage:
        from payplus import PayPlus, SubscriptionManager
        from payplus.subscriptions.storage import MongoDBStorage

        client = PayPlus(api_key="...", secret_key="...")
        storage = MongoDBStorage(db)

        manager = SubscriptionManager(client, storage)

        # Create a subscription (returns a payment link)
        subscription = await manager.create_subscription(
            customer_id="cust_123",
            tier_id="pro",
            callback_url="https://example.com/webhooks/payplus",
            success_url="https://example.com/success",
        )
        # Redirect customer to subscription.payment_page_link
    """

    def __init__(
        self,
        client: "PayPlus",
        storage: Optional["StorageBackend"] = None,
    ):
        self.client = client
        self.storage = storage or InMemoryStorage()

        # Event hooks
        self._hooks: dict[str, list[Callable[..., Any]]] = {
            "subscription.created": [],
            "subscription.activated": [],
            "subscription.canceled": [],
            "subscription.renewed": [],
            "subscription.payment_failed": [],
        }

    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """Register an event hook."""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def _emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to registered hooks."""
        for callback in self._hooks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                pass  # Don't let hook errors break the flow

    # ==================== Customer Management ====================

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Customer:
        """Create a new customer."""
        customer = Customer(
            id=f"cust_{uuid.uuid4().hex[:12]}",
            email=email,
            name=name,
            phone=phone,
            metadata=metadata or {},
        )

        await self.storage.save_customer(customer)
        return customer

    async def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get a customer by ID."""
        return await self.storage.get_customer(customer_id)

    # ==================== Tier Management ====================

    async def create_tier(
        self,
        tier_id: str,
        name: str,
        price: Decimal,
        billing_cycle: BillingCycle = BillingCycle.MONTHLY,
        trial_days: int = 0,
        features: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Tier:
        """Create a pricing tier."""
        tier = Tier(
            id=tier_id,
            name=name,
            price=price,
            billing_cycle=billing_cycle,
            trial_days=trial_days,
            **kwargs,
        )

        if features:
            for f in features:
                tier.add_feature(**f)

        await self.storage.save_tier(tier)
        return tier

    async def get_tier(self, tier_id: str) -> Optional[Tier]:
        """Get a tier by ID."""
        return await self.storage.get_tier(tier_id)

    async def list_tiers(self, active_only: bool = True) -> list[Tier]:
        """List all tiers."""
        return await self.storage.list_tiers(active_only=active_only)

    # ==================== Subscription Management ====================

    async def create_subscription(
        self,
        customer_id: str,
        tier_id: str,
        callback_url: str,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        trial_days: Optional[int] = None,
        number_of_charges: int = 0,
        payment_page_uid: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Subscription:
        """
        Create a subscription by generating a PayPlus payment link with recurring settings.

        The returned subscription includes a `payment_page_link` URL. Redirect the
        customer there to complete payment. Once paid, PayPlus sets up recurring
        billing automatically. Use `handle_webhook_event()` to process payment
        confirmations and update subscription state.

        Args:
            customer_id: Customer ID
            tier_id: Pricing tier ID
            callback_url: Webhook/IPN callback URL (required)
            success_url: Redirect URL on successful payment
            failure_url: Redirect URL on failed payment
            cancel_url: Redirect URL on cancelled payment
            trial_days: Override tier's trial period
            number_of_charges: Total recurring charges (0 = unlimited)
            payment_page_uid: PayPlus payment page UID
            metadata: Additional metadata

        Returns:
            Subscription with payment_page_link set
        """
        # Get customer and tier
        customer = await self.get_customer(customer_id)
        if not customer:
            raise SubscriptionError(f"Customer {customer_id} not found")

        tier = await self.get_tier(tier_id)
        if not tier:
            raise SubscriptionError(f"Tier {tier_id} not found")

        # Create customer on PayPlus if not already created
        if not customer.payplus_customer_uid:
            payplus_result = self.client.customers.add(
                customer_name=customer.name or customer.email,
                email=customer.email,
                phone=customer.phone,
            )
            customer.payplus_customer_uid = (
                payplus_result.get("data", {}).get("customer_uid")
            )
            await self.storage.save_customer(customer)

        # Determine trial period
        effective_trial_days = trial_days if trial_days is not None else tier.trial_days

        # Build recurring settings from tier
        recurring_settings = build_recurring_settings(
            billing_cycle=tier.billing_cycle.value
            if isinstance(tier.billing_cycle, BillingCycle)
            else tier.billing_cycle,
            trial_days=effective_trial_days,
            number_of_charges=number_of_charges,
        )

        # Generate payment link with PayPlus customer UID
        link_kwargs: dict[str, Any] = {}
        if payment_page_uid:
            link_kwargs["payment_page_uid"] = payment_page_uid

        result = self.client.payment_pages.generate_link(
            amount=tier.price,
            currency=tier.currency,
            charge_method=3,  # Recurring Payments
            customer_uid=customer.payplus_customer_uid,
            callback_url=callback_url,
            success_url=success_url,
            failure_url=failure_url,
            cancel_url=cancel_url,
            recurring_settings=recurring_settings,
            **link_kwargs,
        )

        # Extract link data from response
        data = result.get("data", {})
        page_request_uid = data.get("page_request_uid")
        payment_page_link = data.get("payment_page_link")

        # Calculate period end
        now = datetime.utcnow()
        interval, interval_count = tier.billing_cycle.to_interval()
        period_end = self._calculate_period_end(now, interval, interval_count)

        initial_status = SubscriptionStatus.INCOMPLETE
        trial_end = None
        if effective_trial_days > 0:
            trial_end = now + timedelta(days=effective_trial_days)

        # Create local subscription record
        subscription = Subscription(
            id=f"sub_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            tier_id=tier_id,
            status=initial_status,
            amount=tier.price,
            currency=tier.currency,
            billing_cycle=tier.billing_cycle,
            page_request_uid=page_request_uid,
            payment_page_link=payment_page_link,
            trial_start=now if effective_trial_days > 0 else None,
            trial_end=trial_end,
            current_period_start=now,
            current_period_end=period_end,
            metadata=metadata or {},
        )

        await self.storage.save_subscription(subscription)
        self._emit("subscription.created", subscription)

        return subscription

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get a subscription by ID."""
        return await self.storage.get_subscription(subscription_id)

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
        reason: Optional[str] = None,
    ) -> Subscription:
        """
        Cancel a subscription.

        If at_period_end=True, the subscription stays active until the next
        renewal, then gets canceled on PayPlus after the last charge.
        If at_period_end=False, cancels on PayPlus immediately.
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")

        subscription.cancel(at_period_end=at_period_end, reason=reason)

        # Only cancel on PayPlus immediately if not waiting for period end
        if not at_period_end and subscription.payplus_recurring_uid:
            try:
                self.client.recurring.cancel(subscription.payplus_recurring_uid)
            except PayPlusError:
                pass

        await self.storage.save_subscription(subscription)
        self._emit("subscription.canceled", subscription)

        return subscription

    async def change_tier(
        self,
        subscription_id: str,
        new_tier_id: str,
        card_token: Optional[str] = None,
        start_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Subscription:
        """
        Change subscription tier (upgrade/downgrade).

        Updates the recurring payment on PayPlus with the new tier's
        price and billing cycle.

        Args:
            subscription_id: Subscription ID
            new_tier_id: New tier ID
            card_token: PayPlus saved card UID. If not provided, uses the
                        token stored on the subscription from the original payment.
            start_date: Next charge date (YYYY-MM-DD). Defaults to current
                        period end date.
            **kwargs: Additional fields passed to recurring.update()

        Returns:
            Updated subscription
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")

        new_tier = await self.get_tier(new_tier_id)
        if not new_tier:
            raise SubscriptionError(f"Tier {new_tier_id} not found")

        customer = await self.get_customer(subscription.customer_id)
        if not customer:
            raise SubscriptionError(f"Customer {subscription.customer_id} not found")

        effective_card_token = card_token or subscription.payplus_card_token

        # Update on PayPlus if recurring is active
        if (
            subscription.payplus_recurring_uid
            and customer.payplus_customer_uid
            and effective_card_token
        ):
            billing_cycle = (
                new_tier.billing_cycle.value
                if isinstance(new_tier.billing_cycle, BillingCycle)
                else new_tier.billing_cycle
            )
            cycle_map = {
                "daily": (0, 1),
                "weekly": (1, 1),
                "monthly": (2, 1),
                "quarterly": (2, 3),
                "yearly": (2, 12),
            }
            recurring_type, recurring_range = cycle_map.get(billing_cycle, (2, 1))

            effective_start_date = start_date
            if not effective_start_date and subscription.current_period_end:
                effective_start_date = subscription.current_period_end.strftime(
                    "%Y-%m-%d"
                )

            self.client.recurring.update(
                recurring_uid=subscription.payplus_recurring_uid,
                customer_uid=customer.payplus_customer_uid,
                card_token=effective_card_token,
                currency_code=new_tier.currency,
                recurring_type=recurring_type,
                recurring_range=recurring_range,
                start_date=effective_start_date,
                items=[{
                    "price": float(new_tier.price),
                    "quantity": 1,
                }],
                **kwargs,
            )

        subscription.change_tier(new_tier_id, new_tier.price)
        await self.storage.save_subscription(subscription)
        return subscription

    async def pause_subscription(
        self,
        subscription_id: str,
        resume_at: Optional[datetime] = None,
    ) -> Subscription:
        """Pause a subscription."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")

        subscription.pause(resume_at=resume_at)
        await self.storage.save_subscription(subscription)
        return subscription

    async def resume_subscription(self, subscription_id: str) -> Subscription:
        """Resume a paused subscription."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")

        subscription.resume()
        await self.storage.save_subscription(subscription)
        return subscription

    # ==================== Webhook Handling ====================

    async def handle_webhook_event(self, event: "WebhookEvent") -> Optional[Subscription]:
        """
        Handle a webhook event and update subscription state.

        Connect this to your WebhookHandler:

            @webhook_handler.on("payment.success")
            async def on_payment(event):
                await manager.handle_webhook_event(event)

            @webhook_handler.on("recurring.charged")
            async def on_recurring(event):
                await manager.handle_webhook_event(event)

        Args:
            event: Parsed WebhookEvent from WebhookHandler

        Returns:
            Updated subscription if found, None otherwise
        """
        from payplus.webhooks.handler import WebhookEventType

        subscription = None

        # Match by page_request_uid for initial payment
        if event.page_request_uid:
            subscription = await self._find_subscription_by_page_request(
                event.page_request_uid
            )

        # Match by recurring_uid for subsequent charges
        if not subscription and event.recurring_uid:
            subscription = await self._find_subscription_by_recurring_uid(
                event.recurring_uid
            )

        if not subscription:
            return None

        # Store PayPlus identifiers from the callback
        if event.recurring_uid and not subscription.payplus_recurring_uid:
            subscription.payplus_recurring_uid = event.recurring_uid
        if event.raw_data:
            card_info = event.raw_data.get("data", {}).get("card_information", {})
            card_uid = card_info.get("card_uid") or card_info.get("token")
            if card_uid and not subscription.payplus_card_token:
                subscription.payplus_card_token = card_uid

        if event.type in (
            WebhookEventType.PAYMENT_SUCCESS,
            WebhookEventType.RECURRING_CHARGED,
        ):
            if subscription.status == SubscriptionStatus.INCOMPLETE:
                # First payment — activate subscription
                subscription.status = SubscriptionStatus.ACTIVE
                if subscription.trial_end and subscription.trial_end > datetime.utcnow():
                    subscription.status = SubscriptionStatus.TRIALING
                subscription.updated_at = datetime.utcnow()
                await self.storage.save_subscription(subscription)
                self._emit("subscription.activated", subscription)
            else:
                # Renewal — advance period
                subscription.mark_payment_succeeded()
                interval, interval_count = subscription.billing_cycle.to_interval()
                subscription.current_period_start = subscription.current_period_end
                subscription.current_period_end = self._calculate_period_end(
                    subscription.current_period_start, interval, interval_count
                )

                # Cancel on PayPlus if flagged for end-of-period cancellation
                if subscription.cancel_at_period_end:
                    if subscription.payplus_recurring_uid:
                        try:
                            self.client.recurring.cancel(
                                subscription.payplus_recurring_uid
                            )
                        except PayPlusError:
                            pass
                    subscription.status = SubscriptionStatus.CANCELED
                    subscription.ended_at = datetime.utcnow()
                    subscription.updated_at = datetime.utcnow()
                    await self.storage.save_subscription(subscription)
                    self._emit("subscription.canceled", subscription)
                else:
                    await self.storage.save_subscription(subscription)
                    self._emit("subscription.renewed", subscription)

        elif event.type == WebhookEventType.RECURRING_FAILED:
            subscription.mark_payment_failed()
            await self.storage.save_subscription(subscription)
            self._emit("subscription.payment_failed", subscription)

        elif event.type == WebhookEventType.RECURRING_CANCELED:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.ended_at = datetime.utcnow()
            subscription.updated_at = datetime.utcnow()
            await self.storage.save_subscription(subscription)
            self._emit("subscription.canceled", subscription)

        return subscription

    async def _find_subscription_by_page_request(
        self, page_request_uid: str
    ) -> Optional[Subscription]:
        """Find a subscription by its page_request_uid."""
        # Delegate to storage if it supports this query
        if hasattr(self.storage, "get_subscription_by_page_request_uid"):
            return await self.storage.get_subscription_by_page_request_uid(
                page_request_uid
            )
        # Fallback: scan in-memory storage
        if hasattr(self.storage, "subscriptions"):
            for sub in self.storage.subscriptions.values():
                if sub.page_request_uid == page_request_uid:
                    return sub
        return None

    async def _find_subscription_by_recurring_uid(
        self, recurring_uid: str
    ) -> Optional[Subscription]:
        """Find a subscription by its payplus_recurring_uid."""
        if hasattr(self.storage, "get_subscription_by_recurring_uid"):
            return await self.storage.get_subscription_by_recurring_uid(recurring_uid)
        if hasattr(self.storage, "subscriptions"):
            for sub in self.storage.subscriptions.values():
                if sub.payplus_recurring_uid == recurring_uid:
                    return sub
        return None

    # ==================== Helpers ====================

    def _calculate_period_end(
        self,
        start: datetime,
        interval: str,
        interval_count: int,
    ) -> datetime:
        """Calculate the end of a billing period."""
        if interval == "day":
            return start + timedelta(days=interval_count)
        elif interval == "week":
            return start + timedelta(weeks=interval_count)
        elif interval == "month":
            month = start.month + interval_count
            year = start.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            day = min(start.day, 28)
            return start.replace(year=year, month=month, day=day)
        elif interval == "year":
            return start.replace(year=start.year + interval_count)
        else:
            return start + timedelta(days=30 * interval_count)


class InMemoryStorage:
    """Simple in-memory storage for development/testing."""

    def __init__(self) -> None:
        self.customers: dict[str, Customer] = {}
        self.tiers: dict[str, Tier] = {}
        self.subscriptions: dict[str, Subscription] = {}

    async def save_customer(self, customer: Customer) -> None:
        self.customers[customer.id] = customer

    async def get_customer(self, customer_id: str) -> Optional[Customer]:
        return self.customers.get(customer_id)

    async def save_tier(self, tier: Tier) -> None:
        self.tiers[tier.id] = tier

    async def get_tier(self, tier_id: str) -> Optional[Tier]:
        return self.tiers.get(tier_id)

    async def list_tiers(self, active_only: bool = True) -> list[Tier]:
        tiers = list(self.tiers.values())
        if active_only:
            tiers = [t for t in tiers if t.is_active]
        return sorted(tiers, key=lambda t: t.display_order)

    async def save_subscription(self, subscription: Subscription) -> None:
        self.subscriptions[subscription.id] = subscription

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        return self.subscriptions.get(subscription_id)
