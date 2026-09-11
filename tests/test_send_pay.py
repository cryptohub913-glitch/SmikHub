import hashlib
import hmac

from smikhub.services.send_pay import verify_signature

TOKEN = "my-token"


def _sign(body: bytes, token: str = TOKEN) -> str:
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_signature():
    body = b'{"update_type": "invoice_paid"}'
    assert verify_signature(body, _sign(body), TOKEN) is True


def test_verify_signature_rejects_tampered_body():
    body = b'{"a": 1}'
    signature = _sign(body)
    assert verify_signature(b'{"a": 2}', signature, TOKEN) is False


def test_verify_signature_rejects_wrong_token():
    body = b'{"a": 1}'
    signature = _sign(body, token=TOKEN)
    assert verify_signature(body, signature, "a-different-token") is False


def test_verify_signature_rejects_garbage_signature():
    body = b'{"a": 1}'
    assert verify_signature(body, "not-a-real-signature", TOKEN) is False
