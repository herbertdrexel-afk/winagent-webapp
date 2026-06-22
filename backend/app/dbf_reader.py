"""Minimal DBF III/IV reader for *_INV.DBF files."""
import struct
from datetime import date


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        try:
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        except ValueError:
            pass
    return None


def read_dbf(data: bytes) -> list[dict]:
    enc = "cp850"
    num_records = struct.unpack_from("<I", data, 4)[0]
    header_size = struct.unpack_from("<H", data, 8)[0]
    record_size = struct.unpack_from("<H", data, 10)[0]

    fields = []
    offset = 32
    while offset + 32 <= header_size and data[offset] != 0x0D:
        name = data[offset:offset + 11].rstrip(b"\x00").decode("ascii", errors="ignore")
        ftype = chr(data[offset + 11])
        length = data[offset + 16]
        decimal = data[offset + 17]
        fields.append((name, ftype, length, decimal))
        offset += 32

    records = []
    for i in range(num_records):
        rec_start = header_size + i * record_size
        if data[rec_start] == 0x2A:  # deleted
            continue
        pos = rec_start + 1
        row: dict = {}
        for name, ftype, length, decimal in fields:
            raw = data[pos:pos + length].decode(enc, errors="replace")
            if ftype == "C":
                row[name] = raw.strip()
            elif ftype == "N":
                s = raw.strip()
                if s:
                    try:
                        row[name] = float(s) if decimal else int(s)
                    except ValueError:
                        row[name] = None
                else:
                    row[name] = None
            elif ftype == "D":
                row[name] = _parse_date(raw)
            else:
                row[name] = raw.strip()
            pos += length
        records.append(row)
    return records
