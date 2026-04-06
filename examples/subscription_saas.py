"""
Full SaaS subscription example with MongoDB storage.
"""

import asyncio
import os
from decimal import Decimal

from payplus import PayPlus, SubscriptionManager
from payplus.subscriptions.storage import MongoDBStorage
from payplus.webhooks import WebhookHandler


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
    manager.on("subscription.created", lambda s: print(f"Subscription created: {s.id}"))
    manager.on("subscription.activated", lambda s: print(f"Subscription activated: {s.id}"))
    manager.on("subscription.renewed", lambda s: print(f"Subscription renewed: {s.id}"))
    manager.on("subscription.payment_failed", lambda s: print(f"Payment failed for: {s.id}"))

    # ==================== Setup Pricing Tiers ====================
    print("\nCreating pricing tiers...")

    basic_tier = await manager.create_tier(
        tier_id="basic",
        name="Basic",
        price=Decimal("29"),
        trial_days=7,
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": 10},
            {"feature_id": "storage_gb", "name": "Storage (GB)", "included_quantity": 10},
            {"feature_id": "team_members", "name": "Team Members", "included_quantity": 5},
        ],
    )
    print(f"  - {basic_tier.name}: ILS {basic_tier.price}/month (7-day trial)")

    pro_tier = await manager.create_tier(
        tier_id="pro",
        name="Pro",
        price=Decimal("79"),
        trial_days=14,
        is_popular=True,
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": None},
            {"feature_id": "storage_gb", "name": "Storage (GB)", "included_quantity": 100},
            {"feature_id": "team_members", "name": "Team Members", "included_quantity": 20},
            {"feature_id": "api_access", "name": "API Access"},
            {"feature_id": "priority_support", "name": "Priority Support"},
        ],
    )
    print(f"  - {pro_tier.name}: ILS {pro_tier.price}/month (14-day trial)")

    # ==================== Create Customer ====================
    print("\nCreating customer...")

    customer = await manager.create_customer(
        email="demo@example.com",
        name="Demo User",
    )
    print(f"  Customer ID: {customer.id}")

    # ==================== Create Subscription ====================
    print("\nCreating Pro subscription (generates payment link)...")

    subscription = await manager.create_subscription(
        customer_id=customer.id,
        tier_id="pro",
        callback_url="https://example.com/webhooks/payplus",
        success_url="https://example.com/success",
        failure_url="https://example.com/failure",
    )

    print(f"  Subscription ID: {subscription.id}")
    print(f"  Status: {subscription.status}")  # INCOMPLETE until customer pays
    print(f"  Amount: ILS {subscription.amount}/month")
    print(f"  Payment link: {subscription.payment_page_link}")
    print(f"  -> Redirect customer to this link to complete payment")

    # ==================== Webhook Handling ====================
    # In production, this happens when PayPlus sends a webhook after the customer pays.
    # The webhook handler + manager.handle_webhook_event() updates the subscription:
    #
    # webhook_handler = WebhookHandler(client)
    #
    # @webhook_handler.on("payment.success")
    # async def on_payment(event):
    #     sub = await manager.handle_webhook_event(event)
    #     if sub:
    #         print(f"Subscription {sub.id} is now {sub.status}")
    #
    # @webhook_handler.on("recurring.charged")
    # async def on_renewal(event):
    #     await manager.handle_webhook_event(event)
    #
    # @webhook_handler.on("recurring.failed")
    # async def on_failure(event):
    #     await manager.handle_webhook_event(event)

    # ==================== Subscription Operations ====================
    print("\nSubscription operations...")

    # Upgrade to basic (while still incomplete, for demo)
    print("\n  Upgrading tier...")
    subscription = await manager.change_tier(subscription.id, "basic")
    print(f"  New tier: {subscription.tier_id}, amount: ILS {subscription.amount}")

    # Pause
    print("\n  Pausing subscription...")
    subscription = await manager.pause_subscription(subscription.id)
    print(f"  Status: {subscription.status}")

    # Resume
    print("\n  Resuming subscription...")
    subscription = await manager.resume_subscription(subscription.id)
    print(f"  Status: {subscription.status}")

    # Cancel at period end
    print("\n  Scheduling cancellation...")
    subscription = await manager.cancel_subscription(
        subscription.id,
        at_period_end=True,
        reason="Demo completed",
    )
    print(f"  Cancellation reason: {subscription.cancellation_reason}")

    print("\nDemo completed!")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
