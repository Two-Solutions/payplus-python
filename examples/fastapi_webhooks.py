"""
FastAPI webhook handling example.
"""

import os
from fastapi import FastAPI, Request, HTTPException
from payplus import PayPlus
from payplus.webhooks import WebhookHandler, WebhookSignatureError

app = FastAPI(title="PayPlus Webhook Example")

# Initialize PayPlus client
client = PayPlus(
    api_key=os.environ.get("PAYPLUS_API_KEY", "your_api_key"),
    secret_key=os.environ.get("PAYPLUS_SECRET_KEY", "your_secret_key"),
)

# Initialize webhook handler
webhooks = WebhookHandler(client, verify_signature=True)


# Register event handlers
@webhooks.on("payment.success")
async def handle_payment_success(event):
    """Handle successful payment."""
    print(f"✅ Payment succeeded!")
    print(f"   Transaction: {event.transaction_uid}")
    print(f"   Amount: {event.amount} {event.currency}")
    print(f"   Customer: {event.customer_email}")
    
    # Your business logic here:
    # - Update order status
    # - Send confirmation email
    # - Provision service
    # - etc.


@webhooks.on("payment.failure")
async def handle_payment_failure(event):
    """Handle failed payment."""
    print(f"❌ Payment failed!")
    print(f"   Error: {event.status_description}")
    print(f"   Customer: {event.customer_email}")
    
    # Your business logic here:
    # - Update order status
    # - Send notification email
    # - Log for analysis


@webhooks.on("recurring.charged")
async def handle_recurring_charge(event):
    """Handle recurring payment charge."""
    print(f"🔄 Recurring payment charged!")
    print(f"   Recurring UID: {event.recurring_uid}")
    print(f"   Amount: {event.amount} {event.currency}")
    
    # Your business logic here:
    # - Extend subscription
    # - Create invoice
    # - Send receipt


@webhooks.on("recurring.failed")
async def handle_recurring_failure(event):
    """Handle recurring payment failure."""
    print(f"⚠️ Recurring payment failed!")
    print(f"   Recurring UID: {event.recurring_uid}")
    print(f"   Error: {event.status_description}")
    
    # Your business logic here:
    # - Mark subscription as past_due
    # - Send dunning email
    # - Schedule retry


@webhooks.on("token.created")
async def handle_token_created(event):
    """Handle new card token."""
    print(f"💳 Card tokenized!")
    print(f"   Token: {event.card_uid}")
    print(f"   Brand: {event.card_brand}")
    print(f"   Last 4: {event.card_last_four}")
    
    # Your business logic here:
    # - Save token to customer profile
    # - Update payment method


@webhooks.on("*")
async def handle_all_events(event):
    """Catch-all handler for logging."""
    print(f"📨 Webhook received: {event.type.value}")


# Webhook endpoint
@app.post("/webhooks/payplus")
async def payplus_webhook(request: Request):
    """
    PayPlus IPN/Webhook endpoint.
    
    Configure this URL in your PayPlus dashboard:
    https://your-domain.com/webhooks/payplus
    """
    payload = await request.body()
    signature = request.headers.get("X-PayPlus-Signature", "")
    
    try:
        event = await webhooks.handle_async(payload, signature)
        return {
            "received": True,
            "event_id": event.id,
            "event_type": event.type.value,
        }
    except WebhookSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
