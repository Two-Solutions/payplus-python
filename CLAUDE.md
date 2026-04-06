# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python SDK for the PayPlus payment gateway (Israeli payment processor) with a Stripe-like subscription management layer for SaaS applications. Published as `payplus-python` on PyPI.

## Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run tests with coverage
pytest --cov=payplus --cov-report=term-missing

# Run a single test file or test
pytest tests/test_models.py
pytest tests/test_models.py::TestSubscription::test_cancel_subscription

# Lint
ruff check .

# Format
black .

# Type check
mypy payplus
```

## Architecture

The SDK has three main layers:

### 1. API Client (`payplus/client.py` + `payplus/api/`)
`PayPlus` is the core HTTP client wrapping the PayPlus REST API. It uses `httpx` for both sync and async requests. Each API domain (payments, transactions, recurring, payment_pages) is a separate module in `payplus/api/` that extends `BaseAPI` and delegates HTTP calls back to the client.

- Sandbox vs production is controlled by the `sandbox` flag (switches base URL)
- Auth is sent as a JSON-encoded `Authorization` header containing `api_key` and `secret_key`

### 2. Subscription Management (`payplus/subscriptions/`)
A higher-level orchestration layer on top of the API client, modeled after Stripe's subscription patterns:

- **`SubscriptionManager`** — orchestrates customer, tier, and subscription CRUD; handles invoice creation and charging; emits events via hooks (`manager.on("event", callback)`)
- **`BillingService`** — scheduled-job logic for processing renewals, trial conversions, failed payment retries, and end-of-period cancellations. Designed to be called by an external scheduler (Celery, APScheduler, cron)
- **`StorageBackend`** (ABC) — pluggable persistence with `SQLAlchemyStorage`, `MongoDBStorage`, and `InMemoryStorage` implementations. Note: `SQLAlchemyStorage` has several stub methods (save_tier, save_subscription, etc.)
- `InMemoryStorage` lives inside `manager.py` (not in `storage.py`)

### 3. Webhooks (`payplus/webhooks/handler.py`)
`WebhookHandler` parses PayPlus IPN payloads, verifies HMAC-SHA256 signatures, determines event type from response data heuristics, and dispatches to registered handlers. Supports both sync and async dispatch. Includes a `create_fastapi_webhook_router()` helper.

### Models (`payplus/models/`)
All domain models are Pydantic v2 `BaseModel` subclasses: `Customer`, `Subscription`, `Payment`, `Invoice`, `Tier`. Models contain business logic methods (e.g., `Subscription.cancel()`, `Payment.add_refund()`, `Invoice.finalize()`). Entity IDs use the pattern `{prefix}_{uuid_hex[:12]}`.

## Key Conventions

- Python 3.9+ compatibility required
- All async operations use `async/await` (no threading)
- `Decimal` for monetary amounts in models; `float` when interfacing with PayPlus API or MongoDB
- Line length: 100 (both black and ruff)
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Exception hierarchy: `PayPlusError` → `PayPlusAPIError` → `PayPlusAuthError`; separate `SubscriptionError`, `WebhookError` → `WebhookSignatureError`
