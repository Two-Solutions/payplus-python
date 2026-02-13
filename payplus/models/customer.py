"""
Customer model for subscription management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


class CustomerStatus(str, Enum):
    """Customer status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PaymentMethod(BaseModel):
    """Stored payment method (tokenized card)."""
    
    id: str = Field(..., description="Payment method ID")
    token: str = Field(..., description="PayPlus card token (card_uid)")
    card_brand: Optional[str] = Field(None, description="Card brand (Visa, Mastercard, etc.)")
    last_four: Optional[str] = Field(None, description="Last 4 digits of card")
    expiry_month: Optional[str] = Field(None, description="Card expiry month")
    expiry_year: Optional[str] = Field(None, description="Card expiry year")
    holder_name: Optional[str] = Field(None, description="Card holder name")
    is_default: bool = Field(default=False, description="Default payment method")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Customer(BaseModel):
    """
    Customer model for subscription management.
    
    This model tracks customer information, payment methods, and links to
    subscriptions and invoices.
    """
    
    id: str = Field(..., description="Unique customer ID")
    email: EmailStr = Field(..., description="Customer email")
    name: Optional[str] = Field(None, description="Customer full name")
    phone: Optional[str] = Field(None, description="Customer phone")
    company: Optional[str] = Field(None, description="Company name")
    
    # PayPlus integration
    payplus_customer_uid: Optional[str] = Field(None, description="PayPlus customer UID")
    
    # Payment methods
    payment_methods: list[PaymentMethod] = Field(default_factory=list)
    default_payment_method_id: Optional[str] = Field(None)
    
    # Status
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVE)
    
    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = Field(default="IL")
    
    # Tax
    tax_id: Optional[str] = Field(None, description="Tax ID / VAT number")
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_default_payment_method(self) -> Optional[PaymentMethod]:
        """Get the default payment method."""
        if self.default_payment_method_id:
            for pm in self.payment_methods:
                if pm.id == self.default_payment_method_id:
                    return pm
        # Return first payment method if no default set
        if self.payment_methods:
            return self.payment_methods[0]
        return None
    
    def add_payment_method(
        self,
        token: str,
        card_brand: Optional[str] = None,
        last_four: Optional[str] = None,
        expiry_month: Optional[str] = None,
        expiry_year: Optional[str] = None,
        holder_name: Optional[str] = None,
        set_default: bool = True,
    ) -> PaymentMethod:
        """Add a new payment method."""
        import uuid
        
        pm = PaymentMethod(
            id=str(uuid.uuid4()),
            token=token,
            card_brand=card_brand,
            last_four=last_four,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            holder_name=holder_name,
            is_default=set_default,
        )
        
        if set_default:
            for existing in self.payment_methods:
                existing.is_default = False
            self.default_payment_method_id = pm.id
        
        self.payment_methods.append(pm)
        self.updated_at = datetime.utcnow()
        return pm
    
    def remove_payment_method(self, payment_method_id: str) -> bool:
        """Remove a payment method."""
        for i, pm in enumerate(self.payment_methods):
            if pm.id == payment_method_id:
                self.payment_methods.pop(i)
                if self.default_payment_method_id == payment_method_id:
                    self.default_payment_method_id = (
                        self.payment_methods[0].id if self.payment_methods else None
                    )
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    class Config:
        use_enum_values = True
