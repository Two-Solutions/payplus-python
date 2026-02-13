"""
Subscription Manager - Main orchestration layer for subscription management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Optional

from payplus.models.customer import Customer, PaymentMethod
from payplus.models.subscription import Subscription, SubscriptionStatus, BillingCycle
from payplus.models.payment import Payment, PaymentStatus
from payplus.models.invoice import Invoice, InvoiceStatus, InvoiceItem
from payplus.models.tier import Tier
from payplus.exceptions import SubscriptionError, PayPlusError

if TYPE_CHECKING:
    from payplus.client import PayPlus
    from payplus.subscriptions.storage import StorageBackend


class SubscriptionManager:
    """
    High-level subscription management for SaaS applications.
    
    This class orchestrates the creation and management of subscriptions,
    handling the interaction between PayPlus API and your database.
    
    Usage:
        from payplus import PayPlus, SubscriptionManager
        from payplus.subscriptions.storage import SQLAlchemyStorage
        
        client = PayPlus(api_key="...", secret_key="...")
        storage = SQLAlchemyStorage(engine)
        
        manager = SubscriptionManager(client, storage)
        
        # Create a subscription
        subscription = await manager.create_subscription(
            customer_id="cust_123",
            tier_id="pro",
            payment_method_token="token_xxx",
        )
    """
    
    def __init__(
        self,
        client: "PayPlus",
        storage: Optional["StorageBackend"] = None,
    ):
        """
        Initialize the subscription manager.
        
        Args:
            client: PayPlus API client
            storage: Storage backend for persisting data (optional, uses in-memory if not provided)
        """
        self.client = client
        self.storage = storage or InMemoryStorage()
        
        # Event hooks
        self._hooks: dict[str, list[Callable[..., Any]]] = {
            "subscription.created": [],
            "subscription.activated": [],
            "subscription.canceled": [],
            "subscription.renewed": [],
            "subscription.payment_failed": [],
            "invoice.created": [],
            "invoice.paid": [],
            "payment.succeeded": [],
            "payment.failed": [],
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
        """
        Create a new customer.
        
        Args:
            email: Customer email
            name: Customer name
            phone: Customer phone
            metadata: Additional metadata
            
        Returns:
            Created customer
        """
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
    
    async def add_payment_method(
        self,
        customer_id: str,
        token: str,
        card_brand: Optional[str] = None,
        last_four: Optional[str] = None,
        expiry_month: Optional[str] = None,
        expiry_year: Optional[str] = None,
        set_default: bool = True,
    ) -> PaymentMethod:
        """
        Add a payment method to a customer.
        
        Args:
            customer_id: Customer ID
            token: PayPlus card token
            card_brand: Card brand
            last_four: Last 4 digits
            expiry_month: Card expiry month
            expiry_year: Card expiry year
            set_default: Set as default payment method
            
        Returns:
            Created payment method
        """
        customer = await self.get_customer(customer_id)
        if not customer:
            raise SubscriptionError(f"Customer {customer_id} not found")
        
        pm = customer.add_payment_method(
            token=token,
            card_brand=card_brand,
            last_four=last_four,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            set_default=set_default,
        )
        
        await self.storage.save_customer(customer)
        return pm
    
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
        """
        Create a pricing tier.
        
        Args:
            tier_id: Unique tier ID
            name: Tier display name
            price: Price per billing cycle
            billing_cycle: Billing cycle
            trial_days: Trial period in days
            features: List of feature configs
            
        Returns:
            Created tier
        """
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
        payment_method_token: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        trial_days: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Subscription:
        """
        Create a new subscription.
        
        Args:
            customer_id: Customer ID
            tier_id: Pricing tier ID
            payment_method_token: PayPlus card token (for new cards)
            payment_method_id: Existing payment method ID
            trial_days: Override trial period
            metadata: Additional metadata
            
        Returns:
            Created subscription
        """
        # Get customer and tier
        customer = await self.get_customer(customer_id)
        if not customer:
            raise SubscriptionError(f"Customer {customer_id} not found")
        
        tier = await self.get_tier(tier_id)
        if not tier:
            raise SubscriptionError(f"Tier {tier_id} not found")
        
        # Get payment method
        if payment_method_token:
            pm = await self.add_payment_method(customer_id, payment_method_token)
            payment_method_id = pm.id
        elif not payment_method_id:
            pm = customer.get_default_payment_method()
            if pm:
                payment_method_id = pm.id
        
        # Determine trial period
        effective_trial_days = trial_days if trial_days is not None else tier.trial_days
        
        now = datetime.utcnow()
        trial_end = None
        initial_status = SubscriptionStatus.ACTIVE
        
        if effective_trial_days > 0:
            trial_end = now + timedelta(days=effective_trial_days)
            initial_status = SubscriptionStatus.TRIALING
        
        # Calculate period end
        interval, interval_count = tier.billing_cycle.to_interval()
        period_end = self._calculate_period_end(now, interval, interval_count)
        
        # Create subscription
        subscription = Subscription(
            id=f"sub_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            tier_id=tier_id,
            payment_method_id=payment_method_id,
            status=initial_status,
            amount=tier.price,
            currency=tier.currency,
            billing_cycle=tier.billing_cycle,
            trial_start=now if effective_trial_days > 0 else None,
            trial_end=trial_end,
            current_period_start=now,
            current_period_end=period_end,
            metadata=metadata or {},
        )
        
        # If not trialing and we have a payment method, charge immediately
        if initial_status == SubscriptionStatus.ACTIVE and payment_method_id and tier.price > 0:
            invoice = await self._create_subscription_invoice(subscription, tier)
            await self._charge_invoice(invoice, customer, subscription)
        
        await self.storage.save_subscription(subscription)
        self._emit("subscription.created", subscription)
        
        if initial_status == SubscriptionStatus.ACTIVE:
            self._emit("subscription.activated", subscription)
        
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
        
        Args:
            subscription_id: Subscription ID
            at_period_end: Cancel at end of billing period
            reason: Cancellation reason
            
        Returns:
            Updated subscription
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")
        
        subscription.cancel(at_period_end=at_period_end, reason=reason)
        
        # Cancel PayPlus recurring if exists
        if subscription.payplus_recurring_uid:
            try:
                self.client.recurring.cancel(subscription.payplus_recurring_uid)
            except PayPlusError:
                pass  # Don't fail if PayPlus cancel fails
        
        await self.storage.save_subscription(subscription)
        self._emit("subscription.canceled", subscription)
        
        return subscription
    
    async def change_tier(
        self,
        subscription_id: str,
        new_tier_id: str,
        prorate: bool = True,
    ) -> Subscription:
        """
        Change subscription tier (upgrade/downgrade).
        
        Args:
            subscription_id: Subscription ID
            new_tier_id: New tier ID
            prorate: Prorate the change
            
        Returns:
            Updated subscription
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")
        
        new_tier = await self.get_tier(new_tier_id)
        if not new_tier:
            raise SubscriptionError(f"Tier {new_tier_id} not found")
        
        old_amount = subscription.amount
        subscription.change_tier(new_tier_id, new_tier.price)
        
        # Handle proration if upgrading
        if prorate and new_tier.price > old_amount:
            # Calculate prorated amount for remainder of period
            # This is a simplified proration - you may want more sophisticated logic
            pass
        
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
    
    # ==================== Billing ====================
    
    async def _create_subscription_invoice(
        self,
        subscription: Subscription,
        tier: Tier,
    ) -> Invoice:
        """Create an invoice for a subscription."""
        invoice = Invoice(
            id=f"inv_{uuid.uuid4().hex[:12]}",
            customer_id=subscription.customer_id,
            subscription_id=subscription.id,
            status=InvoiceStatus.DRAFT,
            currency=subscription.currency,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            billing_reason="subscription_cycle",
        )
        
        invoice.add_item(
            item_id=f"ii_{uuid.uuid4().hex[:8]}",
            description=f"{tier.name} - {subscription.billing_cycle.value} subscription",
            unit_amount=subscription.amount,
            quantity=1,
            subscription_id=subscription.id,
            tier_id=tier.id,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )
        
        invoice.finalize()
        await self.storage.save_invoice(invoice)
        self._emit("invoice.created", invoice)
        
        return invoice
    
    async def _charge_invoice(
        self,
        invoice: Invoice,
        customer: Customer,
        subscription: Subscription,
    ) -> Payment:
        """Charge an invoice."""
        pm = customer.get_default_payment_method()
        if not pm:
            raise SubscriptionError("No payment method available")
        
        payment = Payment(
            id=f"pay_{uuid.uuid4().hex[:12]}",
            customer_id=customer.id,
            subscription_id=subscription.id,
            invoice_id=invoice.id,
            amount=invoice.total,
            currency=invoice.currency,
            payment_method_id=pm.id,
            card_last_four=pm.last_four,
            card_brand=pm.card_brand,
        )
        
        try:
            # Charge via PayPlus
            result = self.client.transactions.charge(
                token=pm.token,
                amount=float(invoice.total),
                currency=invoice.currency,
                description=f"Invoice {invoice.id}",
            )
            
            transaction_uid = result.get("data", {}).get("transaction_uid")
            approval_number = result.get("data", {}).get("approval_number")
            
            payment.mark_succeeded(
                transaction_uid=transaction_uid,
                approval_number=approval_number,
            )
            
            invoice.mark_paid(payment.id)
            subscription.mark_payment_succeeded()
            
            self._emit("payment.succeeded", payment)
            self._emit("invoice.paid", invoice)
            
        except PayPlusError as e:
            payment.mark_failed(
                failure_code=str(e.status_code) if hasattr(e, "status_code") else None,
                failure_message=str(e),
            )
            subscription.mark_payment_failed()
            
            self._emit("payment.failed", payment)
            self._emit("subscription.payment_failed", subscription)
        
        await self.storage.save_payment(payment)
        await self.storage.save_invoice(invoice)
        await self.storage.save_subscription(subscription)
        
        return payment
    
    async def renew_subscription(self, subscription_id: str) -> Optional[Invoice]:
        """
        Renew a subscription (create invoice and charge).
        
        This is typically called by a scheduled job.
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription or not subscription.will_renew:
            return None
        
        customer = await self.get_customer(subscription.customer_id)
        tier = await self.get_tier(subscription.tier_id)
        
        if not customer or not tier:
            return None
        
        # Update period
        interval, interval_count = subscription.billing_cycle.to_interval()
        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = self._calculate_period_end(
            subscription.current_period_start, interval, interval_count
        )
        
        invoice = await self._create_subscription_invoice(subscription, tier)
        await self._charge_invoice(invoice, customer, subscription)
        
        self._emit("subscription.renewed", subscription)
        
        return invoice
    
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
            # Add months (simplified)
            month = start.month + interval_count
            year = start.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            day = min(start.day, 28)  # Avoid invalid dates
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
        self.invoices: dict[str, Invoice] = {}
        self.payments: dict[str, Payment] = {}
    
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
    
    async def save_invoice(self, invoice: Invoice) -> None:
        self.invoices[invoice.id] = invoice
    
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        return self.invoices.get(invoice_id)
    
    async def save_payment(self, payment: Payment) -> None:
        self.payments[payment.id] = payment
    
    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        return self.payments.get(payment_id)
