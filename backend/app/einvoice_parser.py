"""XRechnung parser — supports UBL 2.1 and CII (UN/CEFACT) formats."""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Namespace maps
_UBL_NS = {
    "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}
_CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


@dataclass
class EInvoiceLine:
    position: int
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    line_total: Decimal
    art_nr: str = ""


@dataclass
class EInvoice:
    invoice_number: str
    invoice_date: date | None
    currency: str
    seller_name: str
    seller_tax_id: str
    buyer_name: str
    buyer_customer_no: str
    net_total: Decimal
    gross_total: Decimal
    lines: list[EInvoiceLine] = field(default_factory=list)
    raw_format: str = ""


def _txt(el, path: str, ns: dict, default="") -> str:
    found = el.find(path, ns)
    return (found.text or "").strip() if found is not None and found.text else default


def _dec(el, path: str, ns: dict, default=Decimal(0)) -> Decimal:
    t = _txt(el, path, ns)
    try:
        return Decimal(t) if t else default
    except Exception:
        return default


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


# ── UBL parser ───────────────────────────────────────────────────────────────
def _parse_ubl(root: ET.Element) -> EInvoice:
    ns = _UBL_NS

    inv_no  = _txt(root, "cbc:ID", ns)
    inv_date = _parse_date(_txt(root, "cbc:IssueDate", ns))
    currency = _txt(root, "cbc:DocumentCurrencyCode", ns, "EUR")

    seller = root.find("cac:AccountingSupplierParty/cac:Party", ns)
    seller_name   = _txt(seller, "cac:PartyName/cbc:Name", ns) if seller is not None else ""
    if not seller_name and seller is not None:
        seller_name = _txt(seller, "cac:PartyLegalEntity/cbc:RegistrationName", ns)
    seller_tax_id = _txt(seller, "cac:PartyTaxScheme/cbc:CompanyID", ns) if seller is not None else ""

    buyer = root.find("cac:AccountingCustomerParty/cac:Party", ns)
    buyer_name = _txt(buyer, "cac:PartyName/cbc:Name", ns) if buyer is not None else ""
    if not buyer_name and buyer is not None:
        buyer_name = _txt(buyer, "cac:PartyLegalEntity/cbc:RegistrationName", ns)
    buyer_cust_no = ""
    if buyer is not None:
        buyer_cust_no = _txt(buyer, "cac:PartyIdentification/cbc:ID", ns)

    net_total   = _dec(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount", ns)
    gross_total = _dec(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", ns)

    lines = []
    for i, line in enumerate(root.findall("cac:InvoiceLine", ns), 1):
        qty     = _dec(line, "cbc:InvoicedQuantity", ns, Decimal(1))
        total   = _dec(line, "cbc:LineExtensionAmount", ns)
        unit    = (line.find("cbc:InvoicedQuantity", ns) or ET.Element("x")).get("unitCode", "")
        desc    = _txt(line, "cac:Item/cbc:Name", ns)
        art_nr  = _txt(line, "cac:Item/cac:SellersItemIdentification/cbc:ID", ns)
        price   = _dec(line, "cac:Price/cbc:PriceAmount", ns)
        lines.append(EInvoiceLine(i, desc, qty, unit, price, total, art_nr))

    return EInvoice(inv_no, inv_date, currency, seller_name, seller_tax_id,
                    buyer_name, buyer_cust_no, net_total, gross_total, lines, "UBL")


# ── CII parser ───────────────────────────────────────────────────────────────
def _parse_cii(root: ET.Element) -> EInvoice:
    ns = _CII_NS

    doc = root.find("rsm:ExchangedDocument", ns)
    inv_no = _txt(doc, "ram:ID", ns) if doc is not None else ""
    date_el = root.find(
        "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString", ns)
    inv_date = _parse_date(date_el.text or "") if date_el is not None else None

    hdr = root.find("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement", ns)
    seller     = hdr.find("ram:SellerTradeParty", ns) if hdr is not None else None
    buyer      = hdr.find("ram:BuyerTradeParty", ns) if hdr is not None else None
    seller_name   = _txt(seller, "ram:Name", ns) if seller is not None else ""
    seller_tax_id = _txt(seller, "ram:SpecifiedTaxRegistration/ram:ID", ns) if seller is not None else ""
    buyer_name    = _txt(buyer, "ram:Name", ns) if buyer is not None else ""
    buyer_cust_no = _txt(buyer, "ram:ID", ns) if buyer is not None else ""

    settlement = root.find(
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement", ns)
    currency    = _txt(settlement, "ram:InvoiceCurrencyCode", ns, "EUR") if settlement is not None else "EUR"
    summary     = settlement.find("ram:SpecifiedTradeSettlementHeaderMonetarySummation", ns) if settlement is not None else None
    net_total   = _dec(summary, "ram:TaxBasisTotalAmount", ns) if summary is not None else Decimal(0)
    gross_total = _dec(summary, "ram:GrandTotalAmount", ns) if summary is not None else Decimal(0)

    lines = []
    for i, item in enumerate(root.findall(
            "rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", ns), 1):
        delivery = item.find("ram:SpecifiedLineTradeDelivery", ns)
        qty = _dec(delivery, "ram:BilledQuantity", ns, Decimal(1)) if delivery is not None else Decimal(1)
        unit_el = delivery.find("ram:BilledQuantity", ns) if delivery is not None else None
        unit = unit_el.get("unitCode", "") if unit_el is not None else ""

        product = item.find("ram:SpecifiedTradeProduct", ns)
        desc   = _txt(product, "ram:Name", ns) if product is not None else ""
        art_nr = _txt(product, "ram:SellerAssignedID", ns) if product is not None else ""

        settle_line = item.find("ram:SpecifiedLineTradeSettlement", ns)
        total = _dec(settle_line,
            "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount", ns) if settle_line is not None else Decimal(0)

        agree = item.find("ram:SpecifiedLineTradeAgreement", ns)
        price = _dec(agree, "ram:NetPriceProductTradePrice/ram:ChargeAmount", ns) if agree is not None else Decimal(0)

        lines.append(EInvoiceLine(i, desc, qty, unit, price, total, art_nr))

    return EInvoice(inv_no, inv_date, currency, seller_name, seller_tax_id,
                    buyer_name, buyer_cust_no, net_total, gross_total, lines, "CII")


# ── Public entry point ────────────────────────────────────────────────────────
def parse_einvoice(xml_bytes: bytes) -> EInvoice:
    root = ET.fromstring(xml_bytes)
    tag = root.tag
    if "CrossIndustryInvoice" in tag:
        return _parse_cii(root)
    if "Invoice" in tag:
        return _parse_ubl(root)
    raise ValueError(f"Unbekanntes XML-Format: {tag}")
