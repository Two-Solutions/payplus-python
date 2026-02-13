"""
Basic payment example - Generate a payment link.
"""

import os
from payplus import PayPlus

# Initialize client
client = PayPlus(
    api_key=os.environ.get("PAYPLUS_API_KEY", "your_api_key"),
    secret_key=os.environ.get("PAYPLUS_SECRET_KEY", "your_secret_key"),
    sandbox=True,  # Use sandbox for testing
)

# Generate a payment link
result = client.payment_pages.generate_link(
    amount=100.00,
    currency="ILS",
    description="Test Payment",
    customer_email="test@example.com",
    customer_name="Test User",
    success_url="https://example.com/success",
    failure_url="https://example.com/failure",
    create_token=True,  # Save card for future use
)

print("Payment Link Generated:")
print(f"URL: {result.get('data', {}).get('payment_page_link')}")
print(f"Request UID: {result.get('data', {}).get('page_request_uid')}")
