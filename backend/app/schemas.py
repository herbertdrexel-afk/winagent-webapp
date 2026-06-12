from datetime import date
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    address: Optional[str] = None
    default_currency: Optional[str] = None
    provision_splits: Optional[Any] = None
    representative_code: Optional[str] = None
    contact_person: Optional[str] = None
    is_active: bool


class SupplierCreate(BaseModel):
    code: str
    name: str
    address: Optional[str] = None
    default_currency: Optional[str] = None
    provision_splits: Optional[Any] = None
    representative_code: Optional[str] = None
    contact_person: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    default_currency: Optional[str] = None
    provision_splits: Optional[Any] = None
    representative_code: Optional[str] = None
    contact_person: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    ku_nr: Optional[str] = None
    name: str
    country_code: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_position: Optional[str] = None
    notes: Optional[str] = None


class CustomerCreate(BaseModel):
    code: str
    name: str
    country_code: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_position: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    country_code: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_position: Optional[str] = None
    notes: Optional[str] = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: Optional[int] = None
    customer_code: Optional[str] = None
    customer_ku_nr: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_number: str
    invoice_date: date
    art_nr: Optional[str] = None
    color: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    discount: Optional[Decimal] = None
    provision_rate: Optional[Decimal] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    total_amount: Decimal
    exchange_rate: Optional[Decimal] = None
    customer_order_no: Optional[str] = None
    notes: Optional[str] = None


class TransactionUpdate(BaseModel):
    customer_id: Optional[int] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    art_nr: Optional[str] = None
    color: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    discount: Optional[Decimal] = None
    provision_rate: Optional[Decimal] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    total_amount: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    customer_order_no: Optional[str] = None
    notes: Optional[str] = None


class CommissionSummaryRow(BaseModel):
    """Eine Zeile der 'Lieferant-Statistik'-Aufstellung: Kunde + Provisionssatz."""
    customer_id: Optional[int] = None
    customer_code: Optional[str] = None
    customer_name: Optional[str] = None
    provision_rate: Optional[Decimal] = None
    currency: Optional[str] = None
    total_amount: Decimal
    provision_amount: Decimal


class CommissionSummaryResponse(BaseModel):
    supplier_code: str
    period_from: date
    period_to: date
    rows: list[CommissionSummaryRow]
    total_amount: Decimal
    total_provision: Decimal


class CommissionStatementCreate(BaseModel):
    supplier_code: str
    period_from: date
    period_to: date


class CommissionStatementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    supplier_id: int
    statement_number: Optional[str] = None
    period_from: date
    period_to: date
    statement_date: Optional[date] = None
    status: str
    total_amount: Optional[Decimal] = None
    total_provision: Optional[Decimal] = None
    currency: Optional[str] = None


class CommissionStatementIssue(BaseModel):
    statement_date: Optional[date] = None  # default: heute
