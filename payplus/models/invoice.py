"""
Invoice model for billing and record-keeping.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Any
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class InvoiceStatus(str, Enum):
    """Invoice status."""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class InvoiceItem(BaseModel):
    """Line item on an invoice."""
    
    id: str = Field(..., description="Line item ID")
    description: str = Field(..., description="Item description")
    quantity: int = Field(default=1)
    unit_amount: Decimal = Field(..., description="Price per unit")
    amount: Decimal = Field(..., description="Total line amount")
    currency: str = Field(default="ILS")
    
    # Period for subscription items
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    # References
    subscription_id: Optional[str] = None
    tier_id: Optional[str] = None
    
    # Proration
    proration: bool = Field(default=False)
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvoiceDiscount(BaseModel):
    """Discount applied to an invoice."""
    
    id: str
    name: str
    amount: Decimal
    percent_off: Optional[Decimal] = None
    coupon_code: Optional[str] = None


class Invoice(BaseModel):
    """
    Invoice model for billing and record-keeping.
    
    Invoices are generated for subscription renewals and one-time charges.
    """
    
    id: str = Field(..., description="Unique invoice ID")
    number: Optional[str] = Field(None, description="Invoice number for display")
    customer_id: str = Field(..., description="Customer ID")
    subscription_id: Optional[str] = Field(None, description="Subscription ID if recurring")
    
    # Status
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)
    
    # Line items
    items: list[InvoiceItem] = Field(default_factory=list)
    
    # Amounts
    subtotal: Decimal = Field(default=Decimal("0"))
    tax: Decimal = Field(default=Decimal("0"))
    tax_percent: Optional[Decimal] = Field(None, description="Tax percentage")
    total: Decimal = Field(default=Decimal("0"))
    amount_due: Decimal = Field(default=Decimal("0"))
    amount_paid: Decimal = Field(default=Decimal("0"))
    amount_remaining: Decimal = Field(default=Decimal("0"))
    currency: str = Field(default="ILS")
    
    # Discounts
    discounts: list[InvoiceDiscount] = Field(default_factory=list)
    total_discount: Decimal = Field(default=Decimal("0"))
    
    # Payment
    payment_id: Optional[str] = Field(None, description="Payment ID when paid")
    payment_intent: Optional[str] = None
    
    # Billing
    billing_reason: Optional[str] = Field(None, description="subscription_create, subscription_cycle, etc.")
    
    # Period
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    # Due date
    due_date: Optional[date] = None
    
    # Customer details snapshot
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_address: Optional[dict[str, str]] = None
    customer_tax_id: Optional[str] = None
    
    # URLs
    hosted_invoice_url: Optional[str] = None
    pdf_url: Optional[str] = None
    
    # Collection
    collection_method: str = Field(default="charge_automatically")
    auto_advance: bool = Field(default=True)
    attempt_count: int = Field(default=0)
    next_payment_attempt: Optional[datetime] = None
    
    # Metadata
    memo: Optional[str] = None
    footer: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    
    def add_item(
        self,
        item_id: str,
        description: str,
        unit_amount: Decimal,
        quantity: int = 1,
        **kwargs: Any,
    ) -> InvoiceItem:
        """Add a line item to the invoice."""
        amount = unit_amount * quantity
        
        item = InvoiceItem(
            id=item_id,
            description=description,
            quantity=quantity,
            unit_amount=unit_amount,
            amount=amount,
            currency=self.currency,
            **kwargs,
        )
        
        self.items.append(item)
        self._recalculate_totals()
        return item
    
    def add_discount(
        self,
        discount_id: str,
        name: str,
        amount: Optional[Decimal] = None,
        percent_off: Optional[Decimal] = None,
        coupon_code: Optional[str] = None,
    ) -> InvoiceDiscount:
        """Add a discount to the invoice."""
        if percent_off:
            calculated_amount = self.subtotal * (percent_off / 100)
        elif amount:
            calculated_amount = amount
        else:
            calculated_amount = Decimal("0")
        
        discount = InvoiceDiscount(
            id=discount_id,
            name=name,
            amount=calculated_amount,
            percent_off=percent_off,
            coupon_code=coupon_code,
        )
        
        self.discounts.append(discount)
        self._recalculate_totals()
        return discount
    
    def _recalculate_totals(self) -> None:
        """Recalculate invoice totals."""
        self.subtotal = sum(item.amount for item in self.items)
        self.total_discount = sum(d.amount for d in self.discounts)
        
        taxable = self.subtotal - self.total_discount
        if self.tax_percent:
            self.tax = taxable * (self.tax_percent / 100)
        
        self.total = taxable + self.tax
        self.amount_remaining = self.total - self.amount_paid
        self.amount_due = self.amount_remaining
        self.updated_at = datetime.utcnow()
    
    def finalize(self) -> None:
        """Finalize the invoice (make it ready for payment)."""
        if self.status != InvoiceStatus.DRAFT:
            return
        
        self._recalculate_totals()
        self.status = InvoiceStatus.OPEN
        self.finalized_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_paid(self, payment_id: str) -> None:
        """Mark the invoice as paid."""
        self.status = InvoiceStatus.PAID
        self.payment_id = payment_id
        self.amount_paid = self.total
        self.amount_remaining = Decimal("0")
        self.amount_due = Decimal("0")
        self.paid_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def void(self) -> None:
        """Void the invoice."""
        self.status = InvoiceStatus.VOID
        self.voided_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_uncollectible(self) -> None:
        """Mark invoice as uncollectible."""
        self.status = InvoiceStatus.UNCOLLECTIBLE
        self.updated_at = datetime.utcnow()
    
    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid."""
        return self.status == InvoiceStatus.PAID
    
    @property
    def is_open(self) -> bool:
        """Check if invoice is open for payment."""
        return self.status == InvoiceStatus.OPEN
    
    class Config:
        use_enum_values = True
