"""
Full SaaS subscription example with MongoDB storage.
"""

import asyncio
import os
from decimal import Decimal

from payplus import PayPlus, SubscriptionManager
from payplus.subscriptions.storage import MongoDBStorage
from payplus.subscriptions import BillingService


async def main():
    # Initialize PayPlus client
    client = PayPlus(
        api_key=os.environ.get("PAYPLUS_API_KEY", "your_api_key"),
        secret_key=os.environ.get("PAYPLUS_SECRET_KEY", "your_secret_key"),
        sandbox=True,
    )
    
    # Setup MongoDB storage
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo = AsyncIOMotorClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
        storage = MongoDBStorage(mongo.payplus_demo)
        await storage.create_indexes()
    except ImportError:
        print("MongoDB not available, using in-memory storage")
        storage = None
    
    # Create subscription manager
    manager = SubscriptionManager(client, storage)
    
    # Register event handlers
    manager.on("subscription.created", lambda s: print(f"✅ Subscription created: {s.id}"))
    manager.on("subscription.activated", lambda s: print(f"🎉 Subscription activated: {s.id}"))
    manager.on("payment.succeeded", lambda p: print(f"💰 Payment received: {p.amount} {p.currency}"))
    manager.on("payment.failed", lambda p: print(f"❌ Payment failed: {p.failure_message}"))
    
    # ==================== Setup Pricing Tiers ====================
    print("\n📦 Creating pricing tiers...")
    
    # Free tier
    free_tier = await manager.create_tier(
        tier_id="free",
        name="Free",
        price=Decimal("0"),
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": 3},
            {"feature_id": "storage_gb", "name": "Storage (GB)", "included_quantity": 1},
            {"feature_id": "team_members", "name": "Team Members", "included_quantity": 1},
        ],
    )
    print(f"  - {free_tier.name}: ₪{free_tier.price}/month")
    
    # Basic tier
    basic_tier = await manager.create_tier(
        tier_id="basic",
        name="Basic",
        price=Decimal("29"),
        trial_days=7,
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": 10},
            {"feature_id": "storage_gb", "name": "Storage (GB)", "included_quantity": 10},
            {"feature_id": "team_members", "name": "Team Members", "included_quantity": 5},
            {"feature_id": "api_access", "name": "API Access"},
        ],
    )
    print(f"  - {basic_tier.name}: ₪{basic_tier.price}/month (7-day trial)")
    
    # Pro tier
    pro_tier = await manager.create_tier(
        tier_id="pro",
        name="Pro",
        price=Decimal("79"),
        trial_days=14,
        is_popular=True,
        annual_discount_percent=Decimal("20"),
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": None},  # Unlimited
            {"feature_id": "storage_gb", "name": "Storage (GB)", "included_quantity": 100},
            {"feature_id": "team_members", "name": "Team Members", "included_quantity": 20},
            {"feature_id": "api_access", "name": "API Access"},
            {"feature_id": "priority_support", "name": "Priority Support"},
            {"feature_id": "custom_domain", "name": "Custom Domain"},
        ],
    )
    print(f"  - {pro_tier.name}: ₪{pro_tier.price}/month (14-day trial, 20% annual discount)")
    
    # Enterprise tier
    enterprise_tier = await manager.create_tier(
        tier_id="enterprise",
        name="Enterprise",
        price=Decimal("199"),
        annual_discount_percent=Decimal("25"),
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": None},
            {"feature_id": "storage_gb", "name": "Storage (GB)", "included_quantity": None},
            {"feature_id": "team_members", "name": "Team Members", "included_quantity": None},
            {"feature_id": "api_access", "name": "API Access"},
            {"feature_id": "priority_support", "name": "Priority Support"},
            {"feature_id": "custom_domain", "name": "Custom Domain"},
            {"feature_id": "sso", "name": "SSO Integration"},
            {"feature_id": "dedicated_support", "name": "Dedicated Account Manager"},
        ],
    )
    print(f"  - {enterprise_tier.name}: ₪{enterprise_tier.price}/month (25% annual discount)")
    
    # ==================== Create Customer ====================
    print("\n👤 Creating customer...")
    
    customer = await manager.create_customer(
        email="demo@example.com",
        name="Demo User",
        metadata={"source": "signup_form", "campaign": "launch_2024"},
    )
    print(f"  Customer ID: {customer.id}")
    print(f"  Email: {customer.email}")
    
    # ==================== Add Payment Method ====================
    print("\n💳 Adding payment method...")
    
    # In production, this token comes from a PayPlus payment page
    # For demo, we'll simulate with a fake token
    demo_token = "demo_card_token_xxx"
    
    payment_method = await manager.add_payment_method(
        customer_id=customer.id,
        token=demo_token,
        card_brand="Visa",
        last_four="4242",
        expiry_month="12",
        expiry_year="2028",
    )
    print(f"  Payment Method: {payment_method.card_brand} ****{payment_method.last_four}")
    
    # ==================== Create Subscription ====================
    print("\n📋 Creating Pro subscription...")
    
    subscription = await manager.create_subscription(
        customer_id=customer.id,
        tier_id="pro",
    )
    
    print(f"  Subscription ID: {subscription.id}")
    print(f"  Status: {subscription.status}")
    print(f"  Amount: ₪{subscription.amount}/month")
    print(f"  Trial ends: {subscription.trial_end}")
    print(f"  Current period: {subscription.current_period_start} - {subscription.current_period_end}")
    
    # ==================== Subscription Operations ====================
    print("\n⚙️ Subscription operations...")
    
    # Check if active
    print(f"  Is active: {subscription.is_active}")
    print(f"  Is trialing: {subscription.is_trialing}")
    
    # Upgrade to enterprise
    print("\n  📈 Upgrading to Enterprise...")
    subscription = await manager.change_tier(subscription.id, "enterprise")
    print(f"  New tier: {subscription.tier_id}")
    print(f"  New amount: ₪{subscription.amount}/month")
    
    # Pause subscription
    print("\n  ⏸️ Pausing subscription...")
    subscription = await manager.pause_subscription(subscription.id)
    print(f"  Status: {subscription.status}")
    
    # Resume subscription
    print("\n  ▶️ Resuming subscription...")
    subscription = await manager.resume_subscription(subscription.id)
    print(f"  Status: {subscription.status}")
    
    # Cancel at period end
    print("\n  🚫 Scheduling cancellation...")
    subscription = await manager.cancel_subscription(
        subscription.id,
        at_period_end=True,
        reason="Demo completed",
    )
    print(f"  Will cancel at: {subscription.current_period_end}")
    print(f"  Cancellation reason: {subscription.cancellation_reason}")
    
    # ==================== Billing Service ====================
    print("\n💵 Billing service...")
    
    billing = BillingService(manager)
    
    # In production, these would run on a schedule
    print("  Processing due renewals...")
    renewed = await billing.process_due_renewals()
    print(f"  Renewed: {len(renewed)} subscriptions")
    
    print("  Processing trial endings...")
    converted = await billing.process_trial_endings()
    print(f"  Converted: {len(converted)} trials")
    
    print("\n✅ Demo completed!")
    
    # Cleanup
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
