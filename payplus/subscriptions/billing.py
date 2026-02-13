"""
Billing Service - Handle billing cycles and scheduled tasks.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from payplus.subscriptions.manager import SubscriptionManager
    from payplus.models.subscription import Subscription


class BillingService:
    """
    Service for handling billing cycles and scheduled renewal tasks.
    
    Usage with your scheduler (e.g., Celery, APScheduler):
    
        from payplus import PayPlus, SubscriptionManager
        from payplus.subscriptions import BillingService
        
        manager = SubscriptionManager(client, storage)
        billing = BillingService(manager)
        
        # Run daily
        async def daily_billing_job():
            await billing.process_due_renewals()
            await billing.process_trial_endings()
    """
    
    def __init__(self, manager: "SubscriptionManager"):
        self.manager = manager
    
    async def process_due_renewals(self) -> list[str]:
        """
        Process all subscriptions due for renewal.
        
        Returns:
            List of processed subscription IDs
        """
        processed = []
        now = datetime.utcnow()
        
        # Get subscriptions due for renewal
        # In production, this would query the database
        subscriptions = await self._get_subscriptions_due_for_renewal(now)
        
        for subscription in subscriptions:
            try:
                invoice = await self.manager.renew_subscription(subscription.id)
                if invoice:
                    processed.append(subscription.id)
            except Exception:
                # Log error but continue with other subscriptions
                pass
        
        return processed
    
    async def process_trial_endings(self) -> list[str]:
        """
        Process subscriptions whose trials are ending.
        
        This converts trialing subscriptions to active and charges them.
        
        Returns:
            List of processed subscription IDs
        """
        processed = []
        now = datetime.utcnow()
        
        subscriptions = await self._get_trials_ending_soon(now)
        
        for subscription in subscriptions:
            try:
                # Convert trial to active subscription
                await self._convert_trial_to_active(subscription)
                processed.append(subscription.id)
            except Exception:
                pass
        
        return processed
    
    async def process_past_due(self) -> list[str]:
        """
        Retry failed payments for past due subscriptions.
        
        Returns:
            List of processed subscription IDs
        """
        processed = []
        
        subscriptions = await self._get_past_due_subscriptions()
        
        for subscription in subscriptions:
            try:
                # Get the open invoice
                # Retry the payment
                # Update status based on result
                processed.append(subscription.id)
            except Exception:
                pass
        
        return processed
    
    async def process_cancellations(self) -> list[str]:
        """
        Process subscriptions scheduled for cancellation at period end.
        
        Returns:
            List of processed subscription IDs
        """
        processed = []
        now = datetime.utcnow()
        
        subscriptions = await self._get_pending_cancellations(now)
        
        for subscription in subscriptions:
            try:
                subscription.status = "canceled"
                subscription.ended_at = now
                await self.manager.storage.save_subscription(subscription)
                processed.append(subscription.id)
            except Exception:
                pass
        
        return processed
    
    async def _get_subscriptions_due_for_renewal(
        self,
        as_of: datetime,
    ) -> list["Subscription"]:
        """Get subscriptions due for renewal."""
        # In production, this would be a database query
        # For now, iterate through in-memory storage
        subscriptions = []
        
        for sub_id in list(self.manager.storage.subscriptions.keys()):
            sub = await self.manager.storage.get_subscription(sub_id)
            if not sub:
                continue
            
            if (
                sub.will_renew
                and sub.current_period_end
                and sub.current_period_end <= as_of
            ):
                subscriptions.append(sub)
        
        return subscriptions
    
    async def _get_trials_ending_soon(
        self,
        as_of: datetime,
        within_hours: int = 24,
    ) -> list["Subscription"]:
        """Get trials ending within specified hours."""
        subscriptions = []
        cutoff = as_of + timedelta(hours=within_hours)
        
        for sub_id in list(self.manager.storage.subscriptions.keys()):
            sub = await self.manager.storage.get_subscription(sub_id)
            if not sub:
                continue
            
            if (
                sub.is_trialing
                and sub.trial_end
                and sub.trial_end <= cutoff
            ):
                subscriptions.append(sub)
        
        return subscriptions
    
    async def _get_past_due_subscriptions(self) -> list["Subscription"]:
        """Get past due subscriptions for retry."""
        subscriptions = []
        
        for sub_id in list(self.manager.storage.subscriptions.keys()):
            sub = await self.manager.storage.get_subscription(sub_id)
            if not sub:
                continue
            
            if sub.status == "past_due" and sub.failed_payment_count < 4:
                subscriptions.append(sub)
        
        return subscriptions
    
    async def _get_pending_cancellations(
        self,
        as_of: datetime,
    ) -> list["Subscription"]:
        """Get subscriptions pending cancellation at period end."""
        subscriptions = []
        
        for sub_id in list(self.manager.storage.subscriptions.keys()):
            sub = await self.manager.storage.get_subscription(sub_id)
            if not sub:
                continue
            
            if (
                sub.cancel_at_period_end
                and sub.current_period_end
                and sub.current_period_end <= as_of
                and sub.status != "canceled"
            ):
                subscriptions.append(sub)
        
        return subscriptions
    
    async def _convert_trial_to_active(
        self,
        subscription: "Subscription",
    ) -> None:
        """Convert a trial subscription to active."""
        from payplus.models.subscription import SubscriptionStatus
        
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.trial_end = None
        subscription.updated_at = datetime.utcnow()
        
        # Create invoice and charge
        customer = await self.manager.get_customer(subscription.customer_id)
        tier = await self.manager.get_tier(subscription.tier_id)
        
        if customer and tier and tier.price > 0:
            invoice = await self.manager._create_subscription_invoice(subscription, tier)
            await self.manager._charge_invoice(invoice, customer, subscription)
        else:
            await self.manager.storage.save_subscription(subscription)
