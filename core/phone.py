import re

IRAN_MOBILE_PATTERN = re.compile(r"^09\d{9}$")


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone.strip())

    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    if not IRAN_MOBILE_PATTERN.match(digits):
        raise ValueError("Invalid Iranian mobile number")

    return digits
