# PayPlus Python SDK

A Python SDK for [PayPlus](https://www.payplus.co.il/) payment gateway with built-in subscription management for SaaS applications.

[![PyPI version](https://badge.fury.io/py/payplus-python.svg)](https://badge.fury.io/py/payplus-python)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Full PayPlus API coverage — payment pages, transactions, recurring payments, customers
- Subscription management — payment-link-based recurring billing for SaaS apps
- Database integration — MongoDB and SQLAlchemy storage backends
- Webhook handling — IPN/webhook integration with HMAC signature verification
- Async support — full async/await for modern Python apps
- Type safe — Pydantic models with full type hints

## Installation

```bash
pip install payplus-python
```

With optional dependencies:

```bash
pip install payplus-python[fastapi]    # FastAPI webhook integration
pip install payplus-python[postgres]   # PostgreSQL storage
pip install payplus-python[mongodb]    # MongoDB storage
```

## Implementation Steps

A step-by-step guide covering the full subscription lifecycle in your app.

### Step 1: Initialize the SDK

```python
from decimal import Decimal
from payplus import PayPlus, SubscriptionManager
from payplus.models.subscription import BillingCycle
from payplus.subscriptions.storage import MongoDBStorage
from payplus.webhooks import WebhookHandler
from motor.motor_asyncio import AsyncIOMotorClient

client = PayPlus(
    api_key="your_api_key",
    secret_key="your_secret_key",
    sandbox=True,
)
mongo = AsyncIOMotorClient("mongodb://localhost:27017")
storage = MongoDBStorage(mongo.your_database)
manager = SubscriptionManager(client, storage)
webhook_handler = WebhookHandler(client)
```

### Step 2: Define your plans (run once on app setup)

```python
await manager.create_tier(
    tier_id="basic",
    name="Basic",
    price=Decimal("29"),
    billing_cycle=BillingCycle.MONTHLY,
    trial_days=7,
)

await manager.create_tier(
    tier_id="pro",
    name="Pro",
    price=Decimal("79"),
    billing_cycle=BillingCycle.MONTHLY,
    trial_days=14,
)
```

### Step 3: User signs up

```python
customer = await manager.create_customer(
    email="user@example.com",
    name="John Doe",
    phone="050-1234567",
)
# Save customer.id in your user record
```

### Step 4: User subscribes to a plan

```python
subscription = await manager.create_subscription(
    customer_id=customer.id,
    tier_id="pro",
    callback_url="https://yourapp.com/webhooks/payplus",
    success_url="https://yourapp.com/subscription/success",
    failure_url="https://yourapp.com/subscription/failure",
)

# Redirect user to complete payment
redirect(subscription.payment_page_link)

# Save subscription.id in your user record
```

Behind the scenes this:

1. Creates the customer on PayPlus (`POST /Customers/Add`) if not already created
2. Generates a payment link with `charge_method=3` and `recurring_settings` derived from the tier
3. Saves the subscription locally with `status=INCOMPLETE`

The user fills in their card details on the PayPlus hosted page. You never touch card data.

### Step 5: Set up the webhook endpoint

```python
from fastapi import FastAPI, Request, HTTPException
from payplus.webhooks import WebhookSignatureError

app = FastAPI()

@app.post("/webhooks/payplus")
async def payplus_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-PayPlus-Signature", "")
    try:
        event = await webhook_handler.handle_async(payload, signature)
        await manager.handle_webhook_event(event)
        return {"received": True}
    except WebhookSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
```

This single endpoint handles every subscription event automatically:

| Webhook event | What happens |
|---|---|
| First payment succeeds | `INCOMPLETE` -> `ACTIVE`, `recurring_uid` stored |
| Recurring charge succeeds | Billing period advanced, status stays `ACTIVE` |
| Recurring charge fails | Status -> `PAST_DUE` (-> `UNPAID` after 4 failures) |
| Recurring canceled | Status -> `CANCELED` |
| Cancel at period end flagged | After last charge, cancels on PayPlus and sets `CANCELED` |

### Step 6: Check access in your app

```python
sub = await manager.get_subscription(subscription_id)
if sub and sub.is_active:
    # User has access
    ...
```

### Step 7: User upgrades plan

```python
await manager.change_tier(subscription.id, new_tier_id="enterprise")
```

This updates the recurring payment on PayPlus with the new tier's price and billing cycle. The card token is saved automatically from the first payment webhook.

### Step 8: User pauses subscription

```python
await manager.pause_subscription(subscription.id)

# Later, resume it
await manager.resume_subscription(subscription.id)
```

### Step 9: User cancels subscription

```python
# Cancel at end of billing period (user keeps access until then)
await manager.cancel_subscription(
    subscription.id,
    at_period_end=True,
    reason="Customer requested",
)

# Or cancel immediately
await manager.cancel_subscription(subscription.id, at_period_end=False)
```

### Step 10: React to lifecycle events (optional)

Register hooks to trigger your own business logic:

```python
manager.on("subscription.activated", lambda sub: send_welcome_email(sub))
manager.on("subscription.renewed", lambda sub: log_renewal(sub))
manager.on("subscription.payment_failed", lambda sub: send_dunning_email(sub))
manager.on("subscription.canceled", lambda sub: handle_offboarding(sub))
```

### Trials

If a tier has `trial_days` set, the subscription flow changes:

- `create_subscription()` sets `jump_payments` in `recurring_settings`, telling PayPlus to wait N days before the first charge
- The subscription starts as `INCOMPLETE` (waiting for the user to enter card details on the payment page)
- When the user completes the payment page, PayPlus validates the card but doesn't charge yet
- The webhook activates the subscription as `TRIALING` (since `trial_end` is in the future)
- After the trial period, PayPlus charges automatically and sends a `recurring.charged` webhook
- `is_active` returns `True` for both `ACTIVE` and `TRIALING` statuses

```python
# Tier with a 14-day trial
await manager.create_tier(
    tier_id="pro",
    name="Pro",
    price=Decimal("79"),
    trial_days=14,  # 14 free days before first charge
)

# After subscription is created and user completes payment page:
# sub.status == "trialing"
# sub.is_active == True
# sub.trial_end == ~14 days from now
```

### How it all fits together

```
User clicks "Subscribe to Pro"
        |
        v
create_subscription()
  - Creates customer on PayPlus
  - Generates payment link with recurring settings
  - Subscription status: INCOMPLETE
        |
        v
User redirected to PayPlus payment page
User enters card details and pays
        |
        v
PayPlus sends webhook to callback_url
        |
        v
handle_webhook_event()
  - Matches webhook to subscription via page_request_uid
  - Saves card token and recurring_uid
  - Sets status: ACTIVE (or TRIALING if trial_days > 0)
        |
        v
Every billing cycle, PayPlus charges automatically
  - recurring.charged  -> period advanced, still ACTIVE
  - recurring.failed   -> PAST_DUE (-> UNPAID after 4 failures)

Lifecycle actions (from your app):
  - change_tier()      -> updates amount on PayPlus
  - pause/resume       -> updates local status
  - cancel(at_period_end=True)  -> flags locally, cancels on PayPlus after last charge
  - cancel(at_period_end=False) -> cancels on PayPlus immediately, status: CANCELED
```

## Direct API Usage

You can also use the PayPlus API directly without the subscription manager:

### Payment Link

```python
result = client.payment_pages.generate_link(
    amount=100.00,
    currency="ILS",
    description="One-time payment",
    customer_email="customer@example.com",
    success_url="https://yourapp.com/success",
    callback_url="https://yourapp.com/webhooks/payplus",
)
print(result["data"]["payment_page_link"])
```

### Payment Link with Recurring

```python
from payplus.api.payment_pages import build_recurring_settings

result = client.payment_pages.generate_link(
    amount=79.00,
    currency="ILS",
    charge_method=3,  # Recurring
    customer_uid="payplus-customer-uid",
    callback_url="https://yourapp.com/webhooks/payplus",
    recurring_settings=build_recurring_settings(
        billing_cycle="monthly",
        trial_days=14,
        number_of_charges=0,  # Unlimited
    ),
)
```

### Create Customer

```python
result = client.customers.add(
    customer_name="John Doe",
    email="john@example.com",
    phone="050-1234567",
)
customer_uid = result["data"]["customer_uid"]
```

### Transactions

```python
# Charge a saved card token
result = client.transactions.charge(
    token="card_token",
    amount=99.00,
    currency="ILS",
)

# Refund
client.transactions.refund(
    transaction_uid=result["data"]["transaction_uid"],
    amount=99.00,
)
```

### Recurring Payments

```python
# Create recurring from token
result = client.recurring.add(
    token="card_token",
    amount=49.00,
    interval="month",
)

# Cancel
client.recurring.cancel(result["data"]["recurring_uid"])
```

## Storage Backends

### MongoDB

```python
from motor.motor_asyncio import AsyncIOMotorClient
from payplus.subscriptions.storage import MongoDBStorage

mongo = AsyncIOMotorClient("mongodb://localhost:27017")
storage = MongoDBStorage(mongo.your_database)
await storage.create_indexes()  # Run once
```

### SQLAlchemy (PostgreSQL, MySQL, SQLite)

```python
from sqlalchemy.ext.asyncio import create_async_engine
from payplus.subscriptions.storage import SQLAlchemyStorage

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
storage = SQLAlchemyStorage(engine)
await storage.create_tables()  # Run once
```

### In-Memory (development/testing)

```python
# Used automatically when no storage is provided
manager = SubscriptionManager(client)
```

## API Reference

### PayPlus Client

| Module | Methods |
|--------|---------|
| `client.customers` | `add()` |
| `client.payment_pages` | `generate_link()`, `get_status()` |
| `client.transactions` | `charge()`, `get()`, `refund()`, `list()` |
| `client.recurring` | `add()`, `update()`, `charge()`, `cancel()`, `get()`, `list()` |
| `client.payments` | `check_card()`, `tokenize()`, `get_token()`, `delete_token()` |

### Subscription Manager

| Method | Description |
|--------|-------------|
| `create_customer()` | Create a new customer |
| `get_customer()` | Get a customer by ID |
| `create_tier()` | Create a pricing tier |
| `get_tier()` | Get a tier by ID |
| `list_tiers()` | List all tiers |
| `create_subscription()` | Create subscription and generate payment link |
| `get_subscription()` | Get a subscription by ID |
| `change_tier()` | Upgrade/downgrade (updates PayPlus recurring) |
| `pause_subscription()` | Pause a subscription |
| `resume_subscription()` | Resume a paused subscription |
| `cancel_subscription()` | Cancel immediately or at period end |
| `handle_webhook_event()` | Process webhook and update subscription state |

## Configuration

```bash
PAYPLUS_API_KEY=your_api_key
PAYPLUS_SECRET_KEY=your_secret_key
PAYPLUS_TERMINAL_UID=your_terminal_uid  # Optional
PAYPLUS_SANDBOX=true  # For testing
```

```python
# Sandbox (restapidev.payplus.co.il)
client = PayPlus(api_key="...", secret_key="...", sandbox=True)

# Production (restapi.payplus.co.il)
client = PayPlus(api_key="...", secret_key="...", sandbox=False)
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

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [PayPlus Documentation](https://docs.payplus.co.il/)
- [GitHub Repository](https://github.com/Two-Solutions/payplus-python)
- [Issue Tracker](https://github.com/Two-Solutions/payplus-python/issues)
