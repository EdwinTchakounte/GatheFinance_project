"""Tiny signed math-captcha.

Replaces the existing site's weak "3 + 1 =" check with a server-issued, signed,
short-lived challenge. The front-end first GETs a challenge ({question, token}),
shows the question, and submits {token, answer} with the form.

This is *one* layer; the form endpoints also use a honeypot field and per-IP
rate-limiting. A real CAPTCHA (hCaptcha / Turnstile) can be added later.
"""
import secrets
import time

from django.core import signing

_SALT = "gathe.forms.captcha"
_MAX_AGE = 60 * 15  # 15 minutes


def new_challenge() -> dict:
    a = secrets.randbelow(9) + 1
    b = secrets.randbelow(9) + 1
    payload = {"a": a, "b": b, "ts": int(time.time())}
    token = signing.dumps(payload, salt=_SALT)
    return {"question": f"{a} + {b}", "token": token}


def verify(token: str, answer) -> bool:
    if not token:
        return False
    try:
        payload = signing.loads(token, salt=_SALT, max_age=_MAX_AGE)
        expected = int(payload["a"]) + int(payload["b"])
        return int(str(answer).strip()) == expected
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError, KeyError):
        return False
