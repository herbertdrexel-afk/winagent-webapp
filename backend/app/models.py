from sqlalchemy import (
    Column, Integer, BigInteger, SmallInteger, String, Numeric, Date, DateTime,
    Boolean, Text, ForeignKey, CHAR, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # "admin" | "user"
    is_approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Country(Base):
    __tablename__ = "countries"
    code = Column(String(3), primary_key=True)
    name = Column(String(50), nullable=False)
    language = Column(CHAR(1))
    vat_rate = Column(Numeric(5, 2))
    invoice_texts = Column(JSONB)


class Representative(Base):
    __tablename__ = "representatives"
    id = Column(Integer, primary_key=True)
    code = Column(String(2), unique=True, nullable=False)
    name = Column(String(60))
    address = Column(JSONB)
    bank_account = Column(String(40))
    bank_blz = Column(String(20))
    currency = Column(String(3))
    mail_to = Column(String(100))
    mail_cc = Column(String(100))
    mail_bcc = Column(String(100))
    is_active = Column(Boolean, default=True)


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    code = Column(String(2), unique=True, nullable=False)
    name = Column(String(60), nullable=False)
    address = Column(String(60))
    country_code = Column(String(3), ForeignKey("countries.code"))
    default_currency = Column(String(3))
    provision_splits = Column(JSONB)
    representative_code = Column(String(2), ForeignKey("representatives.code"))
    contact_person = Column(String(60))
    display_config = Column(JSONB)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)

    transactions = relationship("Transaction", back_populates="supplier")
    statements = relationship("CommissionStatement", back_populates="supplier")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    code = Column(String(6), unique=True, nullable=False)
    ku_nr = Column(String(4))
    name = Column(String(50), nullable=False)
    address_lines = Column(JSONB)
    country_code = Column(String(3), ForeignKey("countries.code"))
    zip = Column(String(8))
    city = Column(String(50))
    phone = Column(String(20))
    fax = Column(String(20))
    email = Column(String(40))
    url = Column(String(40))
    branche = Column(String(20))
    language = Column(CHAR(1))
    tax_number = Column(String(20))
    contact_name = Column(String(24))
    contact_title = Column(String(3))
    contact_position = Column(String(15))
    priority = Column(CHAR(1))
    notes = Column(Text)


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    art_nr = Column(String(20), nullable=False)
    name = Column(String(50))
    notes = Column(String(30))
    color = Column(String(15))
    composition = Column(String(20))
    weight = Column(String(7))
    width = Column(String(7))
    season = Column(String(8))
    category = Column(SmallInteger)
    valid_from = Column(Date)
    prices = Column(JSONB)
    provision_splits = Column(JSONB)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id = Column(Integer, primary_key=True)
    currency = Column(String(3), nullable=False)
    valid_date = Column(Date, nullable=False)
    rate = Column(Numeric(12, 5), nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(BigInteger, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    year = Column(SmallInteger, nullable=False)
    invoice_number = Column(String(10), nullable=False)
    invoice_date = Column(Date, nullable=False)
    art_nr = Column(String(20))
    color = Column(String(15))
    quantity = Column(Numeric(11, 2))
    unit = Column(String(2))
    discount = Column(Numeric(8, 2))
    provision_rate = Column(Numeric(8, 2))
    provision_splits = Column(JSONB)
    price = Column(Numeric(10, 3))
    currency = Column(String(3))
    total_amount = Column(Numeric(13, 2), nullable=False)
    exchange_rate = Column(Numeric(12, 5), default=1)
    customer_order_no = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime)

    supplier = relationship("Supplier", back_populates="transactions")
    customer = relationship("Customer")


class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    year = Column(SmallInteger, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    art_nr = Column(String(20))
    category = Column(SmallInteger)
    currency = Column(String(3))
    quantity_prev_year = Column(Numeric(11, 2))
    price_prev_year = Column(Numeric(11, 2))
    amount_prev_year = Column(Numeric(13, 2))
    quantity_budget = Column(Numeric(11, 2))
    quantity_forecast = Column(Numeric(11, 2))
    price_budget = Column(Numeric(11, 2))
    amount_budget = Column(Numeric(13, 2))
    amount_budget_alt = Column(Numeric(13, 2))


class CommissionStatement(Base):
    __tablename__ = "commission_statements"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    statement_number = Column(String(15), unique=True)
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    statement_date = Column(Date)
    status = Column(String(10), nullable=False, default="draft")
    total_amount = Column(Numeric(13, 2))
    total_provision = Column(Numeric(13, 2))
    currency = Column(String(3))
    created_at = Column(DateTime)

    supplier = relationship("Supplier", back_populates="statements")
    items = relationship("CommissionStatementItem", back_populates="statement",
                          cascade="all, delete-orphan")


class CommissionStatementItem(Base):
    __tablename__ = "commission_statement_items"
    id = Column(BigInteger, primary_key=True)
    statement_id = Column(Integer, ForeignKey("commission_statements.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    provision_rate = Column(Numeric(8, 2))
    total_amount = Column(Numeric(13, 2), nullable=False)
    provision_amount = Column(Numeric(13, 2), nullable=False)
    currency = Column(String(3))
    currency2 = Column(String(3))
    total_amount2 = Column(Numeric(13, 2))
    provision_amount2 = Column(Numeric(13, 2))
    exchange_rate = Column(Numeric(12, 5), default=1)
    rep_code = Column(String(2))
    provision_type = Column(CHAR(1))

    statement = relationship("CommissionStatement", back_populates="items")
    customer = relationship("Customer")


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String(50), primary_key=True)
    value = Column(JSONB, nullable=False)
