"""
Tier model for pricing plans.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from payplus.models.subscription import BillingCycle


class TierType(str, Enum):
    """Tier pricing type."""
    FLAT = "flat"
    PER_UNIT = "per_unit"
    TIERED = "tiered"
    VOLUME = "volume"


class UsageType(str, Enum):
    """Usage tracking type."""
    LICENSED = "licensed"
    METERED = "metered"


class TierFeature(BaseModel):
    """Feature included in a tier."""
    
    id: str = Field(..., description="Feature ID")
    name: str = Field(..., description="Feature name")
    description: Optional[str] = None
    
    # Limits
    included_quantity: Optional[int] = Field(None, description="Included quantity (None = unlimited)")
    limit: Optional[int] = Field(None, description="Hard limit (None = unlimited)")
    
    # Overage
    overage_price: Optional[Decimal] = Field(None, description="Price per unit over included")
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class Tier(BaseModel):
    """
    Pricing tier model for SaaS subscriptions.
    
    Define different tiers (Free, Basic, Pro, Enterprise) with
    features, limits, and pricing.
    """
    
    id: str = Field(..., description="Unique tier ID")
    name: str = Field(..., description="Tier display name")
    description: Optional[str] = None
    
    # Pricing
    price: Decimal = Field(..., description="Price per billing cycle")
    currency: str = Field(default="ILS")
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)
    
    # Pricing type
    tier_type: TierType = Field(default=TierType.FLAT)
    usage_type: UsageType = Field(default=UsageType.LICENSED)
    
    # Per-unit pricing
    unit_amount: Optional[Decimal] = Field(None, description="Price per unit for per_unit pricing")
    minimum_units: int = Field(default=1)
    maximum_units: Optional[int] = None
    
    # Trial
    trial_days: int = Field(default=0, description="Trial period in days")
    
    # Features
    features: list[TierFeature] = Field(default_factory=list)
    
    # Limits
    limits: dict[str, Any] = Field(default_factory=dict, description="Resource limits")
    
    # Display
    display_order: int = Field(default=0, description="Order for display")
    is_popular: bool = Field(default=False, description="Mark as popular/recommended")
    is_active: bool = Field(default=True, description="Tier is available for subscription")
    is_public: bool = Field(default=True, description="Show in public pricing page")
    
    # Annual discount
    annual_discount_percent: Optional[Decimal] = Field(None, description="Discount for annual billing")
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_annual_price(self) -> Decimal:
        """Calculate annual price with discount."""
        yearly_price = self.price * 12
        
        if self.annual_discount_percent:
            discount = yearly_price * (self.annual_discount_percent / 100)
            return yearly_price - discount
        
        return yearly_price
    
    def get_monthly_equivalent(self, for_annual: bool = False) -> Decimal:
        """Get monthly equivalent price."""
        if for_annual:
            return self.get_annual_price() / 12
        return self.price
    
    def add_feature(
        self,
        feature_id: str,
        name: str,
        description: Optional[str] = None,
        included_quantity: Optional[int] = None,
        limit: Optional[int] = None,
        overage_price: Optional[Decimal] = None,
    ) -> TierFeature:
        """Add a feature to this tier."""
        feature = TierFeature(
            id=feature_id,
            name=name,
            description=description,
            included_quantity=included_quantity,
            limit=limit,
            overage_price=overage_price,
        )
        self.features.append(feature)
        self.updated_at = datetime.utcnow()
        return feature
    
    def get_feature(self, feature_id: str) -> Optional[TierFeature]:
        """Get a feature by ID."""
        for feature in self.features:
            if feature.id == feature_id:
                return feature
        return None
    
    def has_feature(self, feature_id: str) -> bool:
        """Check if tier has a feature."""
        return self.get_feature(feature_id) is not None
    
    def set_limit(self, key: str, value: Any) -> None:
        """Set a resource limit."""
        self.limits[key] = value
        self.updated_at = datetime.utcnow()
    
    def get_limit(self, key: str, default: Any = None) -> Any:
        """Get a resource limit."""
        return self.limits.get(key, default)
    
    class Config:
        use_enum_values = True


# Preset tier templates
class TierTemplates:
    """Common tier templates for quick setup."""
    
    @staticmethod
    def free(tier_id: str = "free") -> Tier:
        """Create a free tier template."""
        return Tier(
            id=tier_id,
            name="Free",
            description="Get started with basic features",
            price=Decimal("0"),
            billing_cycle=BillingCycle.MONTHLY,
            display_order=0,
        )
    
    @staticmethod
    def basic(
        tier_id: str = "basic",
        price: Decimal = Decimal("29"),
    ) -> Tier:
        """Create a basic tier template."""
        return Tier(
            id=tier_id,
            name="Basic",
            description="Perfect for individuals and small teams",
            price=price,
            billing_cycle=BillingCycle.MONTHLY,
            trial_days=14,
            display_order=1,
        )
    
    @staticmethod
    def pro(
        tier_id: str = "pro",
        price: Decimal = Decimal("79"),
    ) -> Tier:
        """Create a pro tier template."""
        return Tier(
            id=tier_id,
            name="Pro",
            description="For growing teams that need more power",
            price=price,
            billing_cycle=BillingCycle.MONTHLY,
            trial_days=14,
            is_popular=True,
            display_order=2,
            annual_discount_percent=Decimal("20"),
        )
    
    @staticmethod
    def enterprise(
        tier_id: str = "enterprise",
        price: Decimal = Decimal("199"),
    ) -> Tier:
        """Create an enterprise tier template."""
        return Tier(
            id=tier_id,
            name="Enterprise",
            description="Advanced features for large organizations",
            price=price,
            billing_cycle=BillingCycle.MONTHLY,
            display_order=3,
            annual_discount_percent=Decimal("25"),
        )
