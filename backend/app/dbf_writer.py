"""Minimal DBF III writer for HDUBW.DBF export."""
import struct
from datetime import date


def _encode_field(value, ftype: str, length: int, decimal: int) -> bytes:
    if ftype == "C":
        s = (str(value) if value is not None else "").encode("cp850", errors="replace")
        return s[:length].ljust(length)
    if ftype == "N":
        if value is None:
            return b" " * length
        fmt = f"{{:>{length}.{decimal}f}}"
        return fmt.format(float(value)).encode("ascii")[:length]
    if ftype == "D":
        if value is None:
            return b" " * 8
        if isinstance(value, str):
            value = date.fromisoformat(value)
        return value.strftime("%Y%m%d").encode("ascii")
    return b" " * length


# HDUBW field spec: (name, type, length, decimal)
HDUBW_FIELDS = [
    ("BANK_EIGEN", "C", 4, 0),
    ("F_CODE",     "C", 2, 0),
    ("UBW_DATUM",  "D", 8, 0),
    ("BETRAG",     "N", 10, 2),
    ("WAEHRUNG",   "C", 3, 0),
    ("NAME_KUNDE", "C", 30, 0),
    ("CODE",       "C", 2, 0),
    ("TEXT1",      "C", 30, 0),
    ("TEXT2",      "C", 30, 0),
    ("VON_DATUM",  "D", 8, 0),
    ("BIS_DATUM",  "D", 8, 0),
    ("VALUTASOLL", "D", 8, 0),
    ("SELECTED",   "C", 1, 0),
    ("RE_NUMMER",  "C", 10, 0),
]


def write_hdubw_dbf(records: list[dict]) -> bytes:
    fields = HDUBW_FIELDS
    num_fields = len(fields)
    record_size = 1 + sum(f[2] for f in fields)
    header_size = 32 + 32 * num_fields + 1
    today = date.today()

    # DBF header (32 bytes)
    header = struct.pack(
        "<B3sIHH20s",
        0x03,
        bytes([today.year % 100, today.month, today.day]),
        len(records),
        header_size,
        record_size,
        b"\x00" * 20,
    )

    # Field descriptors (32 bytes each)
    field_bytes = b""
    for name, ftype, length, decimal in fields:
        field_bytes += struct.pack(
            "<11ss4sBB14s",
            name.encode("ascii").ljust(11, b"\x00")[:11],
            ftype.encode("ascii"),
            b"\x00" * 4,
            length,
            decimal,
            b"\x00" * 14,
        )

    # Header terminator
    field_bytes += b"\x0d"

    # Records
    record_bytes = b""
    for rec in records:
        row = b" "  # deletion flag
        for name, ftype, length, decimal in fields:
            row += _encode_field(rec.get(name), ftype, length, decimal)
        record_bytes += row

    return header + field_bytes + record_bytes + b"\x1a"
