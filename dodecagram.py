# dodecagram.py
"""
Dodecagram (base-12) encoder/decoder utilities.

Provides:
- to_base12(n, min_width=0) -> str
- from_base12(s) -> int
- is_valid_dodecagram(s) -> bool
- bytes_to_base12(b) -> str
- base12_to_bytes(s, length=None) -> bytes

Digits mapping: 0-9, a=10, b=11
"""

from typing import Optional

DIGITS = "0123456789ab"
_DIGIT_MAP = {ch: i for i, ch in enumerate(DIGITS)}
__all__ = [
    "DIGITS",
    "to_base12",
    "from_base12",
    "is_valid_dodecagram",
    "bytes_to_base12",
    "base12_to_bytes",
]


def to_base12(n: int, min_width: int = 0) -> str:
    """
    Convert integer `n` to base-12 string using digits 0-9,a,b.
    Supports negative integers. Pads with leading zeros to `min_width`.
    """
    if not isinstance(n, int):
        raise TypeError("to_base12 expects an int")
    if n == 0:
        return "0".rjust(max(0, min_width), "0")
    neg = n < 0
    n_abs = -n if neg else n
    digits = []
    while n_abs:
        digits.append(DIGITS[n_abs % 12])
        n_abs //= 12
    s = "".join(reversed(digits))
    if min_width and len(s) < min_width:
        s = s.rjust(min_width, "0")
    return ("-" + s) if neg else s


def from_base12(s: str) -> int:
    """
    Parse a base-12 string `s` (digits 0-9,a,b). Underscores and spaces allowed and ignored.
    Accepts an optional leading + or - sign.
    Raises ValueError for invalid characters.
    """
    if not isinstance(s, str):
        raise TypeError("from_base12 expects a str")
    s = s.strip()
    if s == "":
        raise ValueError("empty string")
    sign = 1
    if s[0] in ("+", "-"):
        if s[0] == "-":
            sign = -1
        s = s[1:].lstrip()
    # ignore separators
    s = s.replace("_", "").replace(" ", "")
    if s == "":
        raise ValueError("no digits after sign/separators")
    value = 0
    for ch in s:
        ch_lower = ch.lower()
        if ch_lower not in _DIGIT_MAP:
            raise ValueError(f"invalid base-12 digit: {ch}")
        value = value * 12 + _DIGIT_MAP[ch_lower]
    return sign * value


def is_valid_dodecagram(s: str) -> bool:
    """Return True if `s` is a valid base-12 representation (ignoring separators)."""
    try:
        from_base12(s)
        return True
    except Exception:
        return False


def bytes_to_base12(b: bytes) -> str:
    """
    Encode arbitrary bytes to a base-12 integer representation.
    This treats the bytes as a big-endian unsigned integer and returns its base-12 string.
    Empty bytes produce "0".
    """
    if not isinstance(b, (bytes, bytearray)):
        raise TypeError("bytes_to_base12 expects bytes or bytearray")
    if len(b) == 0:
        return "0"
    n = int.from_bytes(b, byteorder="big", signed=False)
    return to_base12(n)


def base12_to_bytes(s: str, length: Optional[int] = None) -> bytes:
    """
    Decode a base-12 string `s` into bytes (big-endian).
    If `length` is provided, the result is padded (or validated) to that many bytes.
    If `length` is None, the minimal number of bytes to hold the integer is returned.
    """
    n = from_base12(s)
    if n < 0:
        raise ValueError("cannot convert negative base-12 value to bytes")
    if n == 0:
        result = b"" if length is None or length == 0 else (b"\x00" * length)
        return result
    min_len = (n.bit_length() + 7) // 8
    if length is None:
        length = min_len
    if length < min_len:
        raise ValueError(f"provided length {length} too small to hold value (needs {min_len})")
    return n.to_bytes(length, byteorder="big")


if __name__ == "__main__":
    # quick smoke tests
    tests = [0, 1, 11, 12, 144, 12345, -37]
    for n in tests:
        s = to_base12(n)
        back = from_base12(s)
        print(f"{n} -> {s} -> {back}")

    b = b"\x01\x02\x03"
    s = bytes_to_base12(b)
    b2 = base12_to_bytes(s)
    print("bytes", b, "->", s, "->", b2)

    # validation examples
    print(is_valid_dodecagram("1ab_0"))
    print(is_valid_dodecagram("xyz"))
    print(is_valid_dodecagram("-  9 8 7"))
    if len(sys.argv) < 2:
        print("Usage: python dodecagram.py <base12-string>")
        raise SystemExit(1)
    for arg in sys.argv[1:]:
        try:
            n = from_base12(arg)
            print(f"{arg} -> {n}")
        except Exception as ex:
            print(f"{arg} : error - {ex}")
            import sys
            sys.exit(1)
            import sys
            if len(sys.argv) < 2:
                print("Usage: python dodecagram.py <base12-string>")
                raise SystemExit(1)
            for arg in sys.argv[1:]:
                try:
                    n = from_base12(arg)
                    print(f"{arg} -> {n}")
                except Exception as ex:
                    print(f"{arg} : error - {ex}")
                    import sys
                    sys.exit(1)
                    
