"""
Tests for PayPlus SDK models.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from payplus.api.payment_pages import build_recurring_settings
from payplus.models.customer import Customer, CustomerStatus
from payplus.models.subscription import BillingCycle, Subscription, SubscriptionStatus
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
        customer.add_payment_method(token="tok_2", set_default=False)

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

    def test_page_request_uid_field(self):
        subscription = Subscription(
            id="sub_123",
            customer_id="cust_123",
            tier_id="pro",
            amount=Decimal("79.00"),
            page_request_uid="f33f7a1f-5ea7-4857-992a-2da95b369f53",
            payment_page_link="https://payments.payplus.co.il/f33f7a1f",
        )

        assert subscription.page_request_uid == "f33f7a1f-5ea7-4857-992a-2da95b369f53"
        assert subscription.payment_page_link == "https://payments.payplus.co.il/f33f7a1f"


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

        tier.add_feature(
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


class TestBuildRecurringSettings:
    """Tests for build_recurring_settings helper."""

    def test_monthly(self):
        settings = build_recurring_settings("monthly")
        assert settings["recurring_type"] == 2
        assert settings["recurring_range"] == 1
        assert settings["jump_payments"] == 0
        assert settings["instant_first_payment"] is True

    def test_weekly(self):
        settings = build_recurring_settings("weekly")
        assert settings["recurring_type"] == 1
        assert settings["recurring_range"] == 1

    def test_daily(self):
        settings = build_recurring_settings("daily")
        assert settings["recurring_type"] == 0
        assert settings["recurring_range"] == 1

    def test_quarterly(self):
        settings = build_recurring_settings("quarterly")
        assert settings["recurring_type"] == 2
        assert settings["recurring_range"] == 3

    def test_yearly(self):
        settings = build_recurring_settings("yearly")
        assert settings["recurring_type"] == 2
        assert settings["recurring_range"] == 12

    def test_with_trial_days(self):
        settings = build_recurring_settings("monthly", trial_days=14)
        assert settings["jump_payments"] == 14

    def test_with_number_of_charges(self):
        settings = build_recurring_settings("monthly", number_of_charges=12)
        assert settings["number_of_charges"] == 12

    def test_with_end_date(self):
        settings = build_recurring_settings("monthly", end_date="2026-12-31")
        assert settings["end_date"] == "2026-12-31"

    def test_without_end_date(self):
        settings = build_recurring_settings("monthly")
        assert "end_date" not in settings

    def test_all_required_fields_present(self):
        settings = build_recurring_settings("monthly")
        required = [
            "recurring_type",
            "recurring_range",
            "number_of_charges",
            "instant_first_payment",
            "start_date_on_payment_date",
            "start_date",
            "jump_payments",
            "successful_invoice",
            "customer_failure_email",
            "send_customer_success_email",
        ]
        for field in required:
            assert field in settings, f"Missing required field: {field}"
