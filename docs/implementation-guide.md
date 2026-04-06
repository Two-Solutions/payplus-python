# Subscription Implementation Guide

Step-by-step guide for adding PayPlus subscriptions to your SaaS app.

## Prerequisites

```bash
pip install payplus-python[fastapi,mongodb]
# or with PostgreSQL:
pip install payplus-python[fastapi,postgres]
```

Environment variables:

```bash
PAYPLUS_API_KEY=your_api_key
PAYPLUS_SECRET_KEY=your_secret_key
PAYPLUS_SANDBOX=true          # remove in production
MONGODB_URI=mongodb://localhost:27017
```

---

## Step 1: Initialize the Stack

Create a module that sets up the PayPlus client, storage, and subscription manager. This should run once at app startup.

```python
# app/billing.py
import os
from payplus import PayPlus, SubscriptionManager
from payplus.subscriptions import BillingService
from payplus.subscriptions.storage import MongoDBStorage
from motor.motor_asyncio import AsyncIOMotorClient

# PayPlus client
payplus = PayPlus(
    api_key=os.environ["PAYPLUS_API_KEY"],
    secret_key=os.environ["PAYPLUS_SECRET_KEY"],
    sandbox=os.environ.get("PAYPLUS_SANDBOX", "false").lower() == "true",
)

# Storage backend
mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
storage = MongoDBStorage(mongo.your_app_db)

# Subscription manager
manager = SubscriptionManager(payplus, storage)

# Billing service (used by scheduled jobs)
billing = BillingService(manager)
```

If using SQLAlchemy instead of MongoDB:

```python
from sqlalchemy.ext.asyncio import create_async_engine
from payplus.subscriptions.storage import SQLAlchemyStorage

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
storage = SQLAlchemyStorage(engine)
```

Run once at startup to create indexes/tables:

```python
# MongoDB
await storage.create_indexes()

# SQLAlchemy
await storage.create_tables()
```

---

## Step 2: Define Pricing Tiers

Create your tiers once (at app startup or via an admin endpoint). These are stored in your database.

```python
# app/setup_tiers.py
from decimal import Decimal
from app.billing import manager

async def create_tiers():
    await manager.create_tier(
        tier_id="free",
        name="Free",
        price=Decimal("0"),
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": 3},
            {"feature_id": "storage_gb", "name": "Storage", "included_quantity": 1},
        ],
    )

    await manager.create_tier(
        tier_id="pro",
        name="Pro",
        price=Decimal("79"),
        trial_days=14,
        is_popular=True,
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": None},  # unlimited
            {"feature_id": "storage_gb", "name": "Storage", "included_quantity": 100},
            {"feature_id": "priority_support", "name": "Priority Support"},
        ],
    )

    await manager.create_tier(
        tier_id="enterprise",
        name="Enterprise",
        price=Decimal("199"),
        features=[
            {"feature_id": "projects", "name": "Projects", "included_quantity": None},
            {"feature_id": "storage_gb", "name": "Storage", "included_quantity": None},
            {"feature_id": "sso", "name": "SSO Integration"},
        ],
    )
```

---

## Step 3: Customer Signup & Payment Method

When a user signs up, create a customer record. Then collect their card via a PayPlus hosted payment page.

### 3a. Create Customer

```python
# In your signup endpoint
from app.billing import manager

customer = await manager.create_customer(
    email=user.email,
    name=user.full_name,
    metadata={"user_id": str(user.id)},  # link to your own user model
)
# Store customer.id alongside your user record
```

### 3b. Generate Payment Page Link

Redirect the user to a PayPlus hosted page to collect their card details. Use `create_token=True` so PayPlus returns a reusable card token.

```python
from app.billing import payplus

result = payplus.payment_pages.generate_link(
    amount=0.00,              # zero-amount for tokenization only
    charge_method=3,          # 3 = token only (no charge)
    currency="ILS",
    customer_email=user.email,
    create_token=True,
    success_url="https://yourapp.com/billing/success",
    failure_url="https://yourapp.com/billing/failure",
    callback_url="https://yourapp.com/webhooks/payplus",  # IPN webhook
)

payment_page_url = result["data"]["payment_page_link"]
# Redirect user to payment_page_url
```

### 3c. Save the Token (via webhook)

When the user completes the payment page, PayPlus sends a webhook with the card token. See Step 5 for webhook setup — the `token.created` handler should save it:

```python
await manager.add_payment_method(
    customer_id=customer_id,
    token=event.card_uid,         # from webhook payload
    card_brand=event.card_brand,
    last_four=event.card_last_four,
)
```

---

## Step 4: Create & Manage Subscriptions

### Create a Subscription

```python
subscription = await manager.create_subscription(
    customer_id=customer.id,
    tier_id="pro",
)
# If the tier has trial_days, status will be "trialing"
# Otherwise it charges immediately and status is "active"
```

### Upgrade / Downgrade

```python
subscription = await manager.change_tier(subscription.id, "enterprise")
```

### Pause / Resume

```python
await manager.pause_subscription(subscription.id)
await manager.resume_subscription(subscription.id)
```

### Cancel

```python
# Cancel at end of current billing period (user keeps access until then)
await manager.cancel_subscription(
    subscription.id,
    at_period_end=True,
    reason="Customer requested",
)

# Cancel immediately
await manager.cancel_subscription(
    subscription.id,
    at_period_end=False,
)
```

---

## Step 5: Webhook Endpoint

Set up a route to receive PayPlus IPN callbacks. Configure this URL in your PayPlus dashboard.

```python
# app/main.py
from fastapi import FastAPI
from payplus.webhooks import WebhookHandler, create_fastapi_webhook_router
from app.billing import payplus, manager

app = FastAPI()

webhooks = WebhookHandler(payplus, verify_signature=True)

@webhooks.on("payment.success")
async def on_payment_success(event):
    # Payment went through — subscription manager already handled status
    # Add your own side effects: confirmation email, analytics, etc.
    print(f"Payment succeeded: {event.transaction_uid}, {event.amount} {event.currency}")

@webhooks.on("payment.failure")
async def on_payment_failure(event):
    # Send dunning email, notify support, etc.
    print(f"Payment failed: {event.status_description}")

@webhooks.on("token.created")
async def on_token_created(event):
    # Save the card token to the customer (see Step 3c)
    # You'll need to map event.customer_email -> your customer_id
    customer = await manager.storage.get_customer_by_email(event.customer_email)
    if customer:
        await manager.add_payment_method(
            customer_id=customer.id,
            token=event.card_uid,
            card_brand=event.card_brand,
            last_four=event.card_last_four,
        )

@webhooks.on("recurring.charged")
async def on_recurring_charged(event):
    print(f"Recurring charge: {event.recurring_uid}")

@webhooks.on("recurring.failed")
async def on_recurring_failed(event):
    print(f"Recurring failed: {event.recurring_uid}")

# Mount the webhook router
router = create_fastapi_webhook_router(webhooks)
app.include_router(router)
```

---

## Step 6: Scheduled Billing Job

The SDK manages the billing cycle, but **you** need to trigger it on a schedule. Run this daily (via Celery beat, APScheduler, cron, etc.).

```python
# app/jobs.py
from app.billing import billing

async def daily_billing_job():
    # 1. Charge subscriptions whose billing period has ended
    renewed = await billing.process_due_renewals()

    # 2. Convert ending trials to paid subscriptions
    converted = await billing.process_trial_endings()

    # 3. Retry failed payments (up to 4 attempts)
    retried = await billing.process_past_due()

    # 4. Finalize subscriptions scheduled for cancellation at period end
    canceled = await billing.process_cancellations()

    print(f"Billing run: {len(renewed)} renewed, {len(converted)} trials converted, "
          f"{len(retried)} retried, {len(canceled)} canceled")
```

### Example: APScheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(daily_billing_job, "cron", hour=3, minute=0)  # run at 3:00 AM
scheduler.start()
```

### Example: Celery Beat

```python
from celery import Celery

app = Celery("billing")

@app.task
def run_billing():
    import asyncio
    asyncio.run(daily_billing_job())

# In celery beat schedule:
# "daily-billing": {"task": "app.jobs.run_billing", "schedule": crontab(hour=3, minute=0)}
```

---

## Step 7: Feature Gating

The SDK doesn't enforce access control — that's your app's responsibility. Check the subscription status and tier features before granting access.

```python
# app/dependencies.py (FastAPI example)
from fastapi import Depends, HTTPException
from app.billing import manager

async def require_active_subscription(user = Depends(get_current_user)):
    """Middleware that checks for an active subscription."""
    subscription = await get_user_subscription(user)

    if not subscription or not subscription.is_active:
        raise HTTPException(status_code=403, detail="Active subscription required")

    return subscription

async def require_feature(feature_id: str):
    """Factory for feature-gating dependencies."""
    async def check(subscription = Depends(require_active_subscription)):
        tier = await manager.get_tier(subscription.tier_id)
        if not tier or not tier.has_feature(feature_id):
            raise HTTPException(status_code=403, detail=f"Feature '{feature_id}' not available on your plan")
        return tier.get_feature(feature_id)
    return check
```

Usage in routes:

```python
@app.post("/projects")
async def create_project(sub = Depends(require_active_subscription)):
    tier = await manager.get_tier(sub.tier_id)
    feature = tier.get_feature("projects")
    if feature and feature.included_quantity is not None:
        current_count = await get_project_count(sub.customer_id)
        if current_count >= feature.included_quantity:
            raise HTTPException(status_code=403, detail="Project limit reached. Upgrade your plan.")
    # ... create the project

@app.post("/sso/configure")
async def configure_sso(feature = Depends(require_feature("sso"))):
    # Only accessible on tiers that include SSO
    ...
```

---

## Step 8: Event Hooks for Business Logic

Register handlers on the subscription manager for side effects like emails, analytics, and access revocation.

```python
# app/events.py
from app.billing import manager

manager.on("subscription.created", lambda sub: send_welcome_email(sub.customer_id))
manager.on("subscription.activated", lambda sub: provision_resources(sub))
manager.on("subscription.canceled", lambda sub: schedule_data_cleanup(sub))
manager.on("subscription.renewed", lambda sub: send_receipt(sub))
manager.on("payment.failed", lambda payment: send_dunning_email(payment))
manager.on("invoice.paid", lambda invoice: generate_pdf_receipt(invoice))
```

---

## Summary: What the SDK Handles vs. What You Build

| SDK handles | You build |
|---|---|
| PayPlus API calls (charges, tokens, recurring) | Webhook route + handler registration |
| Subscription state machine (create, trial, active, pause, cancel) | Scheduled billing job (cron/Celery) |
| Invoice creation and payment processing | Feature gating middleware |
| Storage (MongoDB/SQLAlchemy persistence) | User-to-customer mapping |
| Event emission | Event handler side effects (emails, provisioning) |
| Webhook signature verification & parsing | Frontend payment page redirect flow |
