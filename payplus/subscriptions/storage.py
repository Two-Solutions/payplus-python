"""
Storage backends for subscription data persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from payplus.models.customer import Customer
from payplus.models.subscription import Subscription
from payplus.models.payment import Payment
from payplus.models.invoice import Invoice
from payplus.models.tier import Tier


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    # Customer operations
    @abstractmethod
    async def save_customer(self, customer: Customer) -> None:
        """Save a customer."""
        pass
    
    @abstractmethod
    async def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get a customer by ID."""
        pass
    
    @abstractmethod
    async def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """Get a customer by email."""
        pass
    
    # Tier operations
    @abstractmethod
    async def save_tier(self, tier: Tier) -> None:
        """Save a tier."""
        pass
    
    @abstractmethod
    async def get_tier(self, tier_id: str) -> Optional[Tier]:
        """Get a tier by ID."""
        pass
    
    @abstractmethod
    async def list_tiers(self, active_only: bool = True) -> list[Tier]:
        """List all tiers."""
        pass
    
    # Subscription operations
    @abstractmethod
    async def save_subscription(self, subscription: Subscription) -> None:
        """Save a subscription."""
        pass
    
    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get a subscription by ID."""
        pass
    
    @abstractmethod
    async def list_subscriptions_by_customer(
        self,
        customer_id: str,
        active_only: bool = False,
    ) -> list[Subscription]:
        """List subscriptions for a customer."""
        pass
    
    # Invoice operations
    @abstractmethod
    async def save_invoice(self, invoice: Invoice) -> None:
        """Save an invoice."""
        pass
    
    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get an invoice by ID."""
        pass
    
    @abstractmethod
    async def list_invoices_by_customer(
        self,
        customer_id: str,
        limit: int = 100,
    ) -> list[Invoice]:
        """List invoices for a customer."""
        pass
    
    # Payment operations
    @abstractmethod
    async def save_payment(self, payment: Payment) -> None:
        """Save a payment."""
        pass
    
    @abstractmethod
    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get a payment by ID."""
        pass


class SQLAlchemyStorage(StorageBackend):
    """
    SQLAlchemy storage backend.
    
    Usage:
        from sqlalchemy.ext.asyncio import create_async_engine
        from payplus.subscriptions.storage import SQLAlchemyStorage
        
        engine = create_async_engine("postgresql+asyncpg://...")
        storage = SQLAlchemyStorage(engine)
        
        # Create tables
        await storage.create_tables()
    """
    
    def __init__(self, engine: Any):
        """
        Initialize SQLAlchemy storage.
        
        Args:
            engine: SQLAlchemy async engine
        """
        self.engine = engine
        self._tables_created = False
    
    async def create_tables(self) -> None:
        """Create database tables."""
        from sqlalchemy import (
            MetaData, Table, Column, String, Boolean, DateTime,
            Numeric, Integer, JSON, Text, ForeignKey
        )
        
        metadata = MetaData()
        
        # Customers table
        Table(
            "payplus_customers",
            metadata,
            Column("id", String(50), primary_key=True),
            Column("email", String(255), unique=True, nullable=False),
            Column("name", String(255)),
            Column("phone", String(50)),
            Column("company", String(255)),
            Column("payplus_customer_uid", String(100)),
            Column("payment_methods", JSON, default=[]),
            Column("default_payment_method_id", String(50)),
            Column("status", String(20), default="active"),
            Column("address_line1", String(255)),
            Column("address_line2", String(255)),
            Column("city", String(100)),
            Column("state", String(100)),
            Column("postal_code", String(20)),
            Column("country", String(2), default="IL"),
            Column("tax_id", String(50)),
            Column("metadata", JSON, default={}),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
        
        # Tiers table
        Table(
            "payplus_tiers",
            metadata,
            Column("id", String(50), primary_key=True),
            Column("name", String(100), nullable=False),
            Column("description", Text),
            Column("price", Numeric(10, 2), nullable=False),
            Column("currency", String(3), default="ILS"),
            Column("billing_cycle", String(20), default="monthly"),
            Column("tier_type", String(20), default="flat"),
            Column("usage_type", String(20), default="licensed"),
            Column("trial_days", Integer, default=0),
            Column("features", JSON, default=[]),
            Column("limits", JSON, default={}),
            Column("display_order", Integer, default=0),
            Column("is_popular", Boolean, default=False),
            Column("is_active", Boolean, default=True),
            Column("is_public", Boolean, default=True),
            Column("annual_discount_percent", Numeric(5, 2)),
            Column("metadata", JSON, default={}),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
        
        # Subscriptions table
        Table(
            "payplus_subscriptions",
            metadata,
            Column("id", String(50), primary_key=True),
            Column("customer_id", String(50), ForeignKey("payplus_customers.id")),
            Column("tier_id", String(50), ForeignKey("payplus_tiers.id")),
            Column("payplus_recurring_uid", String(100)),
            Column("payment_method_id", String(50)),
            Column("status", String(30), default="incomplete"),
            Column("amount", Numeric(10, 2), nullable=False),
            Column("currency", String(3), default="ILS"),
            Column("billing_cycle", String(20), default="monthly"),
            Column("trial_start", DateTime),
            Column("trial_end", DateTime),
            Column("current_period_start", DateTime),
            Column("current_period_end", DateTime),
            Column("cancel_at_period_end", Boolean, default=False),
            Column("canceled_at", DateTime),
            Column("ended_at", DateTime),
            Column("cancellation_reason", Text),
            Column("invoice_count", Integer, default=0),
            Column("failed_payment_count", Integer, default=0),
            Column("metadata", JSON, default={}),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
        
        # Invoices table
        Table(
            "payplus_invoices",
            metadata,
            Column("id", String(50), primary_key=True),
            Column("number", String(50)),
            Column("customer_id", String(50), ForeignKey("payplus_customers.id")),
            Column("subscription_id", String(50), ForeignKey("payplus_subscriptions.id")),
            Column("status", String(20), default="draft"),
            Column("items", JSON, default=[]),
            Column("subtotal", Numeric(10, 2), default=0),
            Column("tax", Numeric(10, 2), default=0),
            Column("tax_percent", Numeric(5, 2)),
            Column("total", Numeric(10, 2), default=0),
            Column("amount_due", Numeric(10, 2), default=0),
            Column("amount_paid", Numeric(10, 2), default=0),
            Column("currency", String(3), default="ILS"),
            Column("payment_id", String(50)),
            Column("billing_reason", String(50)),
            Column("period_start", DateTime),
            Column("period_end", DateTime),
            Column("due_date", DateTime),
            Column("metadata", JSON, default={}),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
            Column("finalized_at", DateTime),
            Column("paid_at", DateTime),
        )
        
        # Payments table
        Table(
            "payplus_payments",
            metadata,
            Column("id", String(50), primary_key=True),
            Column("customer_id", String(50), ForeignKey("payplus_customers.id")),
            Column("subscription_id", String(50), ForeignKey("payplus_subscriptions.id")),
            Column("invoice_id", String(50), ForeignKey("payplus_invoices.id")),
            Column("payplus_transaction_uid", String(100)),
            Column("payplus_approval_number", String(50)),
            Column("amount", Numeric(10, 2), nullable=False),
            Column("currency", String(3), default="ILS"),
            Column("payment_method_id", String(50)),
            Column("card_last_four", String(4)),
            Column("card_brand", String(20)),
            Column("status", String(30), default="pending"),
            Column("failure_code", String(50)),
            Column("failure_message", Text),
            Column("refunds", JSON, default=[]),
            Column("amount_refunded", Numeric(10, 2), default=0),
            Column("description", Text),
            Column("metadata", JSON, default={}),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
            Column("paid_at", DateTime),
        )
        
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        
        self._tables_created = True
    
    async def save_customer(self, customer: Customer) -> None:
        """Save a customer."""
        from sqlalchemy import text
        
        data = customer.model_dump()
        data["payment_methods"] = [pm.model_dump() for pm in customer.payment_methods]
        
        async with self.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO payplus_customers (
                        id, email, name, phone, company, payplus_customer_uid,
                        payment_methods, default_payment_method_id, status,
                        address_line1, address_line2, city, state, postal_code,
                        country, tax_id, metadata, created_at, updated_at
                    ) VALUES (
                        :id, :email, :name, :phone, :company, :payplus_customer_uid,
                        :payment_methods, :default_payment_method_id, :status,
                        :address_line1, :address_line2, :city, :state, :postal_code,
                        :country, :tax_id, :metadata, :created_at, :updated_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        email = :email, name = :name, phone = :phone,
                        payment_methods = :payment_methods,
                        default_payment_method_id = :default_payment_method_id,
                        status = :status, metadata = :metadata, updated_at = :updated_at
                """),
                data,
            )
    
    async def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get a customer by ID."""
        from sqlalchemy import text
        
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM payplus_customers WHERE id = :id"),
                {"id": customer_id},
            )
            row = result.fetchone()
            if row:
                return Customer(**dict(row._mapping))
        return None
    
    async def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """Get a customer by email."""
        from sqlalchemy import text
        
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM payplus_customers WHERE email = :email"),
                {"email": email},
            )
            row = result.fetchone()
            if row:
                return Customer(**dict(row._mapping))
        return None
    
    async def save_tier(self, tier: Tier) -> None:
        """Save a tier."""
        # Implementation similar to save_customer
        pass
    
    async def get_tier(self, tier_id: str) -> Optional[Tier]:
        """Get a tier by ID."""
        # Implementation similar to get_customer
        pass
    
    async def list_tiers(self, active_only: bool = True) -> list[Tier]:
        """List all tiers."""
        # Implementation
        return []
    
    async def save_subscription(self, subscription: Subscription) -> None:
        """Save a subscription."""
        pass
    
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get a subscription by ID."""
        pass
    
    async def list_subscriptions_by_customer(
        self,
        customer_id: str,
        active_only: bool = False,
    ) -> list[Subscription]:
        """List subscriptions for a customer."""
        return []
    
    async def save_invoice(self, invoice: Invoice) -> None:
        """Save an invoice."""
        pass
    
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get an invoice by ID."""
        pass
    
    async def list_invoices_by_customer(
        self,
        customer_id: str,
        limit: int = 100,
    ) -> list[Invoice]:
        """List invoices for a customer."""
        return []
    
    async def save_payment(self, payment: Payment) -> None:
        """Save a payment."""
        pass
    
    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get a payment by ID."""
        pass


class MongoDBStorage(StorageBackend):
    """
    MongoDB storage backend using Motor.
    
    Usage:
        from motor.motor_asyncio import AsyncIOMotorClient
        from payplus.subscriptions.storage import MongoDBStorage
        
        client = AsyncIOMotorClient("mongodb://...")
        db = client.your_database
        storage = MongoDBStorage(db)
    """
    
    def __init__(self, database: Any, collection_prefix: str = "payplus_"):
        """
        Initialize MongoDB storage.
        
        Args:
            database: Motor database instance
            collection_prefix: Prefix for collection names
        """
        self.db = database
        self.prefix = collection_prefix
    
    @property
    def customers(self) -> Any:
        return self.db[f"{self.prefix}customers"]
    
    @property
    def tiers(self) -> Any:
        return self.db[f"{self.prefix}tiers"]
    
    @property
    def subscriptions(self) -> Any:
        return self.db[f"{self.prefix}subscriptions"]
    
    @property
    def invoices(self) -> Any:
        return self.db[f"{self.prefix}invoices"]
    
    @property
    def payments(self) -> Any:
        return self.db[f"{self.prefix}payments"]
    
    async def create_indexes(self) -> None:
        """Create MongoDB indexes."""
        await self.customers.create_index("email", unique=True)
        await self.subscriptions.create_index("customer_id")
        await self.subscriptions.create_index("status")
        await self.subscriptions.create_index("current_period_end")
        await self.invoices.create_index("customer_id")
        await self.invoices.create_index("subscription_id")
        await self.payments.create_index("customer_id")
        await self.payments.create_index("invoice_id")
    
    async def save_customer(self, customer: Customer) -> None:
        """Save a customer."""
        data = customer.model_dump()
        data["_id"] = data.pop("id")
        await self.customers.replace_one({"_id": data["_id"]}, data, upsert=True)
    
    async def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get a customer by ID."""
        doc = await self.customers.find_one({"_id": customer_id})
        if doc:
            doc["id"] = doc.pop("_id")
            return Customer(**doc)
        return None
    
    async def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """Get a customer by email."""
        doc = await self.customers.find_one({"email": email})
        if doc:
            doc["id"] = doc.pop("_id")
            return Customer(**doc)
        return None
    
    async def save_tier(self, tier: Tier) -> None:
        """Save a tier."""
        data = tier.model_dump()
        data["_id"] = data.pop("id")
        # Convert Decimal to float for MongoDB
        data["price"] = float(data["price"])
        await self.tiers.replace_one({"_id": data["_id"]}, data, upsert=True)
    
    async def get_tier(self, tier_id: str) -> Optional[Tier]:
        """Get a tier by ID."""
        doc = await self.tiers.find_one({"_id": tier_id})
        if doc:
            doc["id"] = doc.pop("_id")
            return Tier(**doc)
        return None
    
    async def list_tiers(self, active_only: bool = True) -> list[Tier]:
        """List all tiers."""
        query = {"is_active": True} if active_only else {}
        cursor = self.tiers.find(query).sort("display_order", 1)
        tiers = []
        async for doc in cursor:
            doc["id"] = doc.pop("_id")
            tiers.append(Tier(**doc))
        return tiers
    
    async def save_subscription(self, subscription: Subscription) -> None:
        """Save a subscription."""
        data = subscription.model_dump()
        data["_id"] = data.pop("id")
        data["amount"] = float(data["amount"])
        await self.subscriptions.replace_one({"_id": data["_id"]}, data, upsert=True)
    
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get a subscription by ID."""
        doc = await self.subscriptions.find_one({"_id": subscription_id})
        if doc:
            doc["id"] = doc.pop("_id")
            return Subscription(**doc)
        return None
    
    async def list_subscriptions_by_customer(
        self,
        customer_id: str,
        active_only: bool = False,
    ) -> list[Subscription]:
        """List subscriptions for a customer."""
        query: dict[str, Any] = {"customer_id": customer_id}
        if active_only:
            query["status"] = {"$in": ["active", "trialing"]}
        
        cursor = self.subscriptions.find(query).sort("created_at", -1)
        subscriptions = []
        async for doc in cursor:
            doc["id"] = doc.pop("_id")
            subscriptions.append(Subscription(**doc))
        return subscriptions
    
    async def save_invoice(self, invoice: Invoice) -> None:
        """Save an invoice."""
        data = invoice.model_dump()
        data["_id"] = data.pop("id")
        # Convert Decimals
        for key in ["subtotal", "tax", "total", "amount_due", "amount_paid", "amount_remaining"]:
            if key in data:
                data[key] = float(data[key])
        await self.invoices.replace_one({"_id": data["_id"]}, data, upsert=True)
    
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get an invoice by ID."""
        doc = await self.invoices.find_one({"_id": invoice_id})
        if doc:
            doc["id"] = doc.pop("_id")
            return Invoice(**doc)
        return None
    
    async def list_invoices_by_customer(
        self,
        customer_id: str,
        limit: int = 100,
    ) -> list[Invoice]:
        """List invoices for a customer."""
        cursor = self.invoices.find({"customer_id": customer_id}).sort("created_at", -1).limit(limit)
        invoices = []
        async for doc in cursor:
            doc["id"] = doc.pop("_id")
            invoices.append(Invoice(**doc))
        return invoices
    
    async def save_payment(self, payment: Payment) -> None:
        """Save a payment."""
        data = payment.model_dump()
        data["_id"] = data.pop("id")
        data["amount"] = float(data["amount"])
        data["amount_refunded"] = float(data["amount_refunded"])
        await self.payments.replace_one({"_id": data["_id"]}, data, upsert=True)
    
    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get a payment by ID."""
        doc = await self.payments.find_one({"_id": payment_id})
        if doc:
            doc["id"] = doc.pop("_id")
            return Payment(**doc)
        return None
