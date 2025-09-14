# dodecagram.py

DIGITS = "0123456789ab"

def to_base12(n):
    if n == 0:
        return "0"
    digits = []
    while n:
        digits.append(DIGITS[n % 12])
        n //= 12
    return ''.join(reversed(digits))
