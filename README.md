# PayPlus Python SDK

A comprehensive Python SDK for [PayPlus](https://www.payplus.co.il/) payment gateway with built-in subscription management for SaaS applications.

[![PyPI version](https://badge.fury.io/py/payplus-sdk.svg)](https://badge.fury.io/py/payplus-sdk)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🔌 **Full PayPlus API Coverage** - Payment pages, transactions, recurring payments, tokenization
- 💳 **Subscription Management** - Stripe-like subscription handling for SaaS apps
- 🗄️ **Database Integration** - SQLAlchemy and MongoDB storage backends
- 🔔 **Webhook Handling** - Easy IPN/webhook integration with signature verification
- ⚡ **Async Support** - Full async/await support for modern Python apps
- 🏗️ **Type Safe** - Full type hints with Pydantic models

## Installation

```bash
pip install payplus-sdk
```

With optional dependencies:

```bash
# For FastAPI webhook integration
pip install payplus-sdk[fastapi]

# For PostgreSQL storage
pip install payplus-sdk[postgres]

# For MongoDB storage
pip install payplus-sdk[mongodb]

# All extras
pip install payplus-sdk[fastapi,postgres,mongodb]
```

## Quick Start

### Basic Payment Link

```python
from payplus import PayPlus

# Initialize client
client = PayPlus(
    api_key="your_api_key",
    secret_key="your_secret_key",
    sandbox=True  # Use sandbox for testing
)

# Generate a payment link
result = client.payment_pages.generate_link(
    amount=100.00,
    currency="ILS",
    description="Premium Plan - Monthly",
    customer_email="customer@example.com",
    success_url="https://yourapp.com/success",
    failure_url="https://yourapp.com/failure",
    create_token=True  # Save card for future charges
)

print(f"Payment URL: {result['data']['payment_page_link']}")
```

### Direct Card Charge (with token)

```python
# Charge a saved card
result = client.transactions.charge(
    token="card_token_from_payment",
    amount=99.00,
    currency="ILS",
    description="Monthly subscription"
)

print(f"Transaction: {result['data']['transaction_uid']}")
```

### Recurring Payments

```python
# Create a recurring payment
result = client.recurring.add(
    token="card_token",
    amount=49.00,
    currency="ILS",
    interval="month",
    interval_count=1,
    description="Pro Plan"
)

recurring_uid = result['data']['recurring_uid']

# Cancel recurring
client.recurring.cancel(recurring_uid)
```

## Subscription Management

The SDK includes a complete subscription management system for SaaS applications:

```python
from payplus import PayPlus, SubscriptionManager
from payplus.subscriptions.storage import MongoDBStorage
from motor.motor_asyncio import AsyncIOMotorClient
from decimal import Decimal

# Setup
client = PayPlus(api_key="...", secret_key="...")
mongo = AsyncIOMotorClient("mongodb://localhost:27017")
storage = MongoDBStorage(mongo.your_database)

manager = SubscriptionManager(client, storage)

# Create pricing tiers
await manager.create_tier(
    tier_id="free",
    name="Free",
    price=Decimal("0"),
    features=[
        {"feature_id": "projects", "name": "Projects", "included_quantity": 3},
        {"feature_id": "storage", "name": "Storage", "included_quantity": 1},
    ]
)

await manager.create_tier(
    tier_id="pro",
    name="Pro",
    price=Decimal("79"),
    trial_days=14,
    features=[
        {"feature_id": "projects", "name": "Projects", "included_quantity": None},  # Unlimited
        {"feature_id": "storage", "name": "Storage", "included_quantity": 100},
        {"feature_id": "priority_support", "name": "Priority Support"},
    ]
)

# Create a customer
customer = await manager.create_customer(
    email="user@example.com",
    name="John Doe"
)

# Add payment method (from PayPlus token)
await manager.add_payment_method(
    customer_id=customer.id,
    token="card_token_from_payplus",
    card_brand="Visa",
    last_four="4242"
)

# Create subscription
subscription = await manager.create_subscription(
    customer_id=customer.id,
    tier_id="pro"  # Will start with 14-day trial
)

print(f"Subscription: {subscription.id}")
print(f"Status: {subscription.status}")  # "trialing"
print(f"Trial ends: {subscription.trial_end}")
```

### Subscription Lifecycle

```python
# Upgrade/downgrade
await manager.change_tier(subscription.id, "enterprise")

# Pause subscription
await manager.pause_subscription(subscription.id)

# Resume subscription
await manager.resume_subscription(subscription.id)

# Cancel at period end
await manager.cancel_subscription(
    subscription.id,
    at_period_end=True,
    reason="Customer requested"
)

# Cancel immediately
await manager.cancel_subscription(
    subscription.id,
    at_period_end=False
)
```

### Event Hooks

```python
# Register event handlers
manager.on("subscription.created", lambda sub: print(f"New sub: {sub.id}"))
manager.on("payment.succeeded", lambda payment: print(f"Paid: {payment.amount}"))
manager.on("payment.failed", lambda payment: send_dunning_email(payment))
manager.on("subscription.canceled", lambda sub: handle_cancellation(sub))
```

### Billing Service (for scheduled jobs)

```python
from payplus.subscriptions import BillingService

billing = BillingService(manager)

# Run daily via your scheduler (Celery, APScheduler, cron, etc.)
async def daily_billing_job():
    # Process subscription renewals
    renewed = await billing.process_due_renewals()
    
    # Convert ending trials to paid
    converted = await billing.process_trial_endings()
    
    # Retry failed payments
    retried = await billing.process_past_due()
    
    # Finalize cancellations
    canceled = await billing.process_cancellations()
```

## Webhook Handling

```python
from fastapi import FastAPI, Request
from payplus import PayPlus
from payplus.webhooks import WebhookHandler

app = FastAPI()
client = PayPlus(api_key="...", secret_key="...")
webhooks = WebhookHandler(client)

@webhooks.on("payment.success")
async def handle_payment_success(event):
    print(f"Payment succeeded: {event.transaction_uid}")
    print(f"Amount: {event.amount} {event.currency}")
    # Update your database, send confirmation email, etc.

@webhooks.on("payment.failure")
async def handle_payment_failure(event):
    print(f"Payment failed: {event.status_description}")
    # Send retry notification, update subscription status, etc.

@webhooks.on("recurring.charged")
async def handle_recurring_charge(event):
    print(f"Recurring payment: {event.recurring_uid}")

@app.post("/webhooks/payplus")
async def payplus_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-PayPlus-Signature", "")
    
    event = await webhooks.handle_async(payload, signature)
    return {"received": True}
```

Or use the built-in router:

```python
from payplus.webhooks import create_fastapi_webhook_router

router = create_fastapi_webhook_router(webhooks)
app.include_router(router)
```

## Storage Backends

### MongoDB

```python
from motor.motor_asyncio import AsyncIOMotorClient
from payplus.subscriptions.storage import MongoDBStorage

client = AsyncIOMotorClient("mongodb://localhost:27017")
storage = MongoDBStorage(client.your_database)

# Create indexes (run once)
await storage.create_indexes()
```

### SQLAlchemy (PostgreSQL, MySQL, SQLite)

```python
from sqlalchemy.ext.asyncio import create_async_engine
from payplus.subscriptions.storage import SQLAlchemyStorage

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
storage = SQLAlchemyStorage(engine)

# Create tables (run once)
await storage.create_tables()
```

## Models

The SDK provides Pydantic models for all entities:

```python
from payplus.models import (
    Customer,
    Subscription, SubscriptionStatus, BillingCycle,
    Payment, PaymentStatus,
    Invoice, InvoiceStatus,
    Tier, TierFeature,
)

# Create a tier programmatically
from payplus.models.tier import TierTemplates

free_tier = TierTemplates.free()
pro_tier = TierTemplates.pro(price=Decimal("99"))
```

## API Reference

### PayPlus Client

| Module | Methods |
|--------|---------|
| `client.payment_pages` | `generate_link()`, `get_status()` |
| `client.transactions` | `charge()`, `get()`, `refund()`, `list()` |
| `client.recurring` | `add()`, `charge()`, `cancel()`, `get()`, `list()` |
| `client.payments` | `check_card()`, `tokenize()`, `get_token()`, `delete_token()` |

### Subscription Manager

| Method | Description |
|--------|-------------|
| `create_customer()` | Create a new customer |
| `add_payment_method()` | Add a payment method to customer |
| `create_tier()` | Create a pricing tier |
| `create_subscription()` | Create a new subscription |
| `cancel_subscription()` | Cancel a subscription |
| `change_tier()` | Upgrade/downgrade subscription |
| `pause_subscription()` | Pause a subscription |
| `resume_subscription()` | Resume a paused subscription |

## Configuration

### Environment Variables

```bash
PAYPLUS_API_KEY=your_api_key
PAYPLUS_SECRET_KEY=your_secret_key
PAYPLUS_TERMINAL_UID=your_terminal_uid  # Optional
PAYPLUS_SANDBOX=true  # For testing
```

### Sandbox vs Production

```python
# Sandbox (testing)
client = PayPlus(
    api_key="...",
    secret_key="...",
    sandbox=True  # Uses restapidev.payplus.co.il
)

# Production
client = PayPlus(
    api_key="...",
    secret_key="...",
    sandbox=False  # Uses restapi.payplus.co.il
)
```

## Error Handling

```python
from payplus.exceptions import (
    PayPlusError,
    PayPlusAPIError,
    PayPlusAuthError,
    SubscriptionError,
    WebhookSignatureError,
)

try:
    result = client.transactions.charge(token="...", amount=100)
except PayPlusAuthError:
    print("Invalid API credentials")
except PayPlusAPIError as e:
    print(f"API error [{e.status_code}]: {e.message}")
except PayPlusError as e:
    print(f"General error: {e}")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [PayPlus Documentation](https://docs.payplus.co.il/)
- [GitHub Repository](https://github.com/Two-Solutions/payplus-python)
- [Issue Tracker](https://github.com/Two-Solutions/payplus-python/issues)
