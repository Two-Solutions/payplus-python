"""
Payment model for tracking payments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    """Payment method type."""
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    DIRECT_DEBIT = "direct_debit"


class RefundReason(str, Enum):
    """Refund reason codes."""
    REQUESTED_BY_CUSTOMER = "requested_by_customer"
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    SERVICE_NOT_PROVIDED = "service_not_provided"
    OTHER = "other"


class Refund(BaseModel):
    """Refund record."""
    
    id: str
    amount: Decimal
    currency: str = "ILS"
    reason: Optional[RefundReason] = None
    status: str = "succeeded"
    payplus_refund_uid: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Payment(BaseModel):
    """
    Payment model for tracking individual payments.
    
    This tracks both successful and failed payment attempts,
    linked to subscriptions and invoices.
    """
    
    id: str = Field(..., description="Unique payment ID")
    customer_id: str = Field(..., description="Customer ID")
    subscription_id: Optional[str] = Field(None, description="Subscription ID if recurring")
    invoice_id: Optional[str] = Field(None, description="Invoice ID")
    
    # PayPlus integration
    payplus_transaction_uid: Optional[str] = Field(None, description="PayPlus transaction UID")
    payplus_approval_number: Optional[str] = Field(None, description="Credit card approval number")
    
    # Amount
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(default="ILS", description="Currency code")
    
    # Payment method
    payment_method_type: PaymentMethod = Field(default=PaymentMethod.CARD)
    payment_method_id: Optional[str] = Field(None, description="Payment method ID used")
    card_last_four: Optional[str] = Field(None, description="Last 4 digits of card")
    card_brand: Optional[str] = Field(None, description="Card brand")
    
    # Status
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    failure_code: Optional[str] = Field(None, description="Failure code if failed")
    failure_message: Optional[str] = Field(None, description="Failure message")
    
    # Refunds
    refunds: list[Refund] = Field(default_factory=list)
    amount_refunded: Decimal = Field(default=Decimal("0"))
    
    # Installments
    installments: int = Field(default=1, description="Number of installments")
    installment_number: Optional[int] = Field(None, description="Current installment number")
    
    # Description
    description: Optional[str] = None
    statement_descriptor: Optional[str] = None
    
    # Receipt
    receipt_email: Optional[str] = None
    receipt_url: Optional[str] = None
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    
    @property
    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status == PaymentStatus.SUCCEEDED
    
    @property
    def is_refunded(self) -> bool:
        """Check if payment was fully refunded."""
        return self.status == PaymentStatus.REFUNDED
    
    @property
    def net_amount(self) -> Decimal:
        """Get net amount after refunds."""
        return self.amount - self.amount_refunded
    
    def add_refund(
        self,
        refund_id: str,
        amount: Decimal,
        reason: Optional[RefundReason] = None,
        payplus_refund_uid: Optional[str] = None,
    ) -> Refund:
        """Add a refund to this payment."""
        refund = Refund(
            id=refund_id,
            amount=amount,
            currency=self.currency,
            reason=reason,
            payplus_refund_uid=payplus_refund_uid,
        )
        self.refunds.append(refund)
        self.amount_refunded += amount
        self.updated_at = datetime.utcnow()
        
        if self.amount_refunded >= self.amount:
            self.status = PaymentStatus.REFUNDED
        else:
            self.status = PaymentStatus.PARTIALLY_REFUNDED
        
        return refund
    
    def mark_succeeded(
        self,
        transaction_uid: Optional[str] = None,
        approval_number: Optional[str] = None,
    ) -> None:
        """Mark payment as succeeded."""
        self.status = PaymentStatus.SUCCEEDED
        self.paid_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        if transaction_uid:
            self.payplus_transaction_uid = transaction_uid
        if approval_number:
            self.payplus_approval_number = approval_number
    
    def mark_failed(
        self,
        failure_code: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> None:
        """Mark payment as failed."""
        self.status = PaymentStatus.FAILED
        self.failure_code = failure_code
        self.failure_message = failure_message
        self.updated_at = datetime.utcnow()
    
    class Config:
        use_enum_values = True
