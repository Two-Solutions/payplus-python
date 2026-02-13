"""
Tests for PayPlus SDK models.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from payplus.models.customer import Customer, CustomerStatus, PaymentMethod
from payplus.models.subscription import Subscription, SubscriptionStatus, BillingCycle
from payplus.models.payment import Payment, PaymentStatus
from payplus.models.invoice import Invoice, InvoiceStatus
from payplus.models.tier import Tier, TierTemplates


class TestCustomer:
    """Tests for Customer model."""
    
    def test_create_customer(self):
        customer = Customer(
            id="cust_123",
            email="test@example.com",
            name="Test User",
        )
        
        assert customer.id == "cust_123"
        assert customer.email == "test@example.com"
        assert customer.status == CustomerStatus.ACTIVE
    
    def test_add_payment_method(self):
        customer = Customer(
            id="cust_123",
            email="test@example.com",
        )
        
        pm = customer.add_payment_method(
            token="tok_123",
            card_brand="Visa",
            last_four="4242",
            set_default=True,
        )
        
        assert len(customer.payment_methods) == 1
        assert pm.token == "tok_123"
        assert pm.is_default is True
        assert customer.default_payment_method_id == pm.id
    
    def test_get_default_payment_method(self):
        customer = Customer(
            id="cust_123",
            email="test@example.com",
        )
        
        pm1 = customer.add_payment_method(token="tok_1", set_default=True)
        pm2 = customer.add_payment_method(token="tok_2", set_default=False)
        
        default = customer.get_default_payment_method()
        assert default.id == pm1.id
    
    def test_remove_payment_method(self):
        customer = Customer(
            id="cust_123",
            email="test@example.com",
        )
        
        pm = customer.add_payment_method(token="tok_123")
        assert len(customer.payment_methods) == 1
        
        result = customer.remove_payment_method(pm.id)
        assert result is True
        assert len(customer.payment_methods) == 0


class TestSubscription:
    """Tests for Subscription model."""
    
    def test_create_subscription(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
        )
        
        assert subscription.id == "sub_123"
        assert subscription.status == SubscriptionStatus.INCOMPLETE
    
    def test_subscription_is_active(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
            status=SubscriptionStatus.ACTIVE,
        )
        
        assert subscription.is_active is True
    
    def test_subscription_trialing(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
            status=SubscriptionStatus.TRIALING,
            trial_end=datetime.utcnow() + timedelta(days=14),
        )
        
        assert subscription.is_trialing is True
        assert subscription.is_active is True  # Trialing is considered active
    
    def test_cancel_subscription(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
            status=SubscriptionStatus.ACTIVE,
        )
        
        subscription.cancel(at_period_end=True, reason="Customer request")
        
        assert subscription.cancel_at_period_end is True
        assert subscription.cancellation_reason == "Customer request"
        assert subscription.canceled_at is not None
        assert subscription.status == SubscriptionStatus.ACTIVE  # Still active until period end
    
    def test_cancel_immediately(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
            status=SubscriptionStatus.ACTIVE,
        )
        
        subscription.cancel(at_period_end=False)
        
        assert subscription.status == SubscriptionStatus.CANCELED
        assert subscription.ended_at is not None
    
    def test_pause_resume(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
            status=SubscriptionStatus.ACTIVE,
        )
        
        subscription.pause()
        assert subscription.status == SubscriptionStatus.PAUSED
        assert subscription.paused_at is not None
        
        subscription.resume()
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.paused_at is None


class TestPayment:
    """Tests for Payment model."""
    
    def test_create_payment(self):
        payment = Payment(
            id="pay_123",
            customer_id="cust_123",
            amount=Decimal("100.00"),
        )
        
        assert payment.id == "pay_123"
        assert payment.status == PaymentStatus.PENDING
    
    def test_mark_succeeded(self):
        payment = Payment(
            id="pay_123",
            customer_id="cust_123",
            amount=Decimal("100.00"),
        )
        
        payment.mark_succeeded(transaction_uid="tx_123", approval_number="123456")
        
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.payplus_transaction_uid == "tx_123"
        assert payment.paid_at is not None
    
    def test_mark_failed(self):
        payment = Payment(
            id="pay_123",
            customer_id="cust_123",
            amount=Decimal("100.00"),
        )
        
        payment.mark_failed(failure_code="card_declined", failure_message="Card was declined")
        
        assert payment.status == PaymentStatus.FAILED
        assert payment.failure_code == "card_declined"
    
    def test_refund(self):
        payment = Payment(
            id="pay_123",
            customer_id="cust_123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCEEDED,
        )
        
        payment.add_refund(
            refund_id="ref_123",
            amount=Decimal("50.00"),
        )
        
        assert payment.amount_refunded == Decimal("50.00")
        assert payment.status == PaymentStatus.PARTIALLY_REFUNDED
        assert payment.net_amount == Decimal("50.00")
    
    def test_full_refund(self):
        payment = Payment(
            id="pay_123",
            customer_id="cust_123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCEEDED,
        )
        
        payment.add_refund(refund_id="ref_123", amount=Decimal("100.00"))
        
        assert payment.status == PaymentStatus.REFUNDED


class TestInvoice:
    """Tests for Invoice model."""
    
    def test_create_invoice(self):
        invoice = Invoice(
            id="inv_123",
            customer_id="cust_123",
        )
        
        assert invoice.id == "inv_123"
        assert invoice.status == InvoiceStatus.DRAFT
    
    def test_add_items(self):
        invoice = Invoice(
            id="inv_123",
            customer_id="cust_123",
        )
        
        invoice.add_item(
            item_id="ii_1",
            description="Pro Plan",
            unit_amount=Decimal("79.00"),
            quantity=1,
        )
        
        assert len(invoice.items) == 1
        assert invoice.subtotal == Decimal("79.00")
        assert invoice.total == Decimal("79.00")
    
    def test_finalize_invoice(self):
        invoice = Invoice(
            id="inv_123",
            customer_id="cust_123",
        )
        
        invoice.add_item(
            item_id="ii_1",
            description="Pro Plan",
            unit_amount=Decimal("79.00"),
        )
        
        invoice.finalize()
        
        assert invoice.status == InvoiceStatus.OPEN
        assert invoice.finalized_at is not None
    
    def test_mark_paid(self):
        invoice = Invoice(
            id="inv_123",
            customer_id="cust_123",
            total=Decimal("79.00"),
            amount_due=Decimal("79.00"),
            status=InvoiceStatus.OPEN,
        )
        
        invoice.mark_paid(payment_id="pay_123")
        
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.payment_id == "pay_123"
        assert invoice.amount_paid == Decimal("79.00")


class TestTier:
    """Tests for Tier model."""
    
    def test_create_tier(self):
        tier = Tier(
            id="pro",
            name="Pro",
            price=Decimal("79.00"),
        )
        
        assert tier.id == "pro"
        assert tier.price == Decimal("79.00")
        assert tier.billing_cycle == BillingCycle.MONTHLY
    
    def test_annual_price(self):
        tier = Tier(
            id="pro",
            name="Pro",
            price=Decimal("79.00"),
            annual_discount_percent=Decimal("20"),
        )
        
        annual = tier.get_annual_price()
        expected = Decimal("79.00") * 12 * Decimal("0.80")
        assert annual == expected
    
    def test_add_feature(self):
        tier = Tier(
            id="pro",
            name="Pro",
            price=Decimal("79.00"),
        )
        
        feature = tier.add_feature(
            feature_id="projects",
            name="Projects",
            included_quantity=100,
        )
        
        assert len(tier.features) == 1
        assert tier.has_feature("projects")
        assert tier.get_feature("projects").included_quantity == 100
    
    def test_tier_templates(self):
        free = TierTemplates.free()
        assert free.price == Decimal("0")
        
        pro = TierTemplates.pro(price=Decimal("99"))
        assert pro.price == Decimal("99")
        assert pro.is_popular is True


class TestBillingCycle:
    """Tests for BillingCycle."""
    
    def test_to_interval(self):
        assert BillingCycle.MONTHLY.to_interval() == ("month", 1)
        assert BillingCycle.YEARLY.to_interval() == ("year", 1)
        assert BillingCycle.QUARTERLY.to_interval() == ("month", 3)
