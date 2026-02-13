"""
Subscription model for SaaS subscription management.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Any
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


class BillingCycle(str, Enum):
    """Billing cycle interval."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    
    def to_interval(self) -> tuple[str, int]:
        """Convert to interval and count."""
        mapping = {
            BillingCycle.DAILY: ("day", 1),
            BillingCycle.WEEKLY: ("week", 1),
            BillingCycle.MONTHLY: ("month", 1),
            BillingCycle.QUARTERLY: ("month", 3),
            BillingCycle.YEARLY: ("year", 1),
        }
        return mapping[self]


class SubscriptionItem(BaseModel):
    """Item in a subscription (for metered billing)."""
    
    id: str
    tier_id: str
    quantity: int = 1
    unit_amount: Decimal = Decimal("0")
    
    @property
    def total_amount(self) -> Decimal:
        return self.unit_amount * self.quantity


class Subscription(BaseModel):
    """
    Subscription model for managing SaaS subscriptions.
    
    This model tracks the subscription lifecycle, billing, and links
    to the customer and tier.
    """
    
    id: str = Field(..., description="Unique subscription ID")
    customer_id: str = Field(..., description="Customer ID")
    tier_id: str = Field(..., description="Pricing tier ID")
    
    # PayPlus integration
    payplus_recurring_uid: Optional[str] = Field(None, description="PayPlus recurring payment UID")
    payment_method_id: Optional[str] = Field(None, description="Payment method ID used")
    
    # Status
    status: SubscriptionStatus = Field(default=SubscriptionStatus.INCOMPLETE)
    
    # Pricing
    amount: Decimal = Field(..., description="Subscription amount per period")
    currency: str = Field(default="ILS", description="Currency code")
    
    # Billing
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)
    billing_anchor: Optional[int] = Field(None, description="Day of month for billing (1-28)")
    
    # Items (for metered/quantity-based billing)
    items: list[SubscriptionItem] = Field(default_factory=list)
    
    # Trial
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    
    # Period tracking
    current_period_start: datetime = Field(default_factory=datetime.utcnow)
    current_period_end: Optional[datetime] = None
    
    # Cancellation
    cancel_at_period_end: bool = Field(default=False)
    canceled_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    
    # Pause
    pause_collection: Optional[dict[str, Any]] = None
    paused_at: Optional[datetime] = None
    
    # Counters
    invoice_count: int = Field(default=0)
    failed_payment_count: int = Field(default=0)
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
    
    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == SubscriptionStatus.TRIALING
    
    @property
    def is_canceled(self) -> bool:
        """Check if subscription is canceled."""
        return self.status == SubscriptionStatus.CANCELED or self.cancel_at_period_end
    
    @property
    def will_renew(self) -> bool:
        """Check if subscription will renew at period end."""
        return self.is_active and not self.cancel_at_period_end
    
    def cancel(self, at_period_end: bool = True, reason: Optional[str] = None) -> None:
        """Cancel the subscription."""
        self.cancel_at_period_end = at_period_end
        self.cancellation_reason = reason
        self.canceled_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        if not at_period_end:
            self.status = SubscriptionStatus.CANCELED
            self.ended_at = datetime.utcnow()
    
    def pause(self, resume_at: Optional[datetime] = None) -> None:
        """Pause the subscription."""
        self.status = SubscriptionStatus.PAUSED
        self.paused_at = datetime.utcnow()
        self.pause_collection = {
            "paused_at": self.paused_at.isoformat(),
            "resume_at": resume_at.isoformat() if resume_at else None,
        }
        self.updated_at = datetime.utcnow()
    
    def resume(self) -> None:
        """Resume a paused subscription."""
        if self.status == SubscriptionStatus.PAUSED:
            self.status = SubscriptionStatus.ACTIVE
            self.paused_at = None
            self.pause_collection = None
            self.updated_at = datetime.utcnow()
    
    def mark_payment_failed(self) -> None:
        """Mark a payment as failed."""
        self.failed_payment_count += 1
        self.updated_at = datetime.utcnow()
        
        # Update status based on failure count
        if self.failed_payment_count >= 4:
            self.status = SubscriptionStatus.UNPAID
        else:
            self.status = SubscriptionStatus.PAST_DUE
    
    def mark_payment_succeeded(self) -> None:
        """Mark a payment as succeeded."""
        self.failed_payment_count = 0
        self.status = SubscriptionStatus.ACTIVE
        self.invoice_count += 1
        self.updated_at = datetime.utcnow()
    
    def change_tier(self, new_tier_id: str, new_amount: Decimal) -> None:
        """Change subscription tier."""
        self.tier_id = new_tier_id
        self.amount = new_amount
        self.updated_at = datetime.utcnow()
    
    class Config:
        use_enum_values = True
