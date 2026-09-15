import hmac, hashlib, json
from urllib.parse import parse_qsl, unquote
from fastapi import HTTPException
from smikhub.config import BOT_TOKEN

def validate_telegram_webapp_data(init_data: str):
    if not init_data:
        raise HTTPException(status_code=401, detail="No initData provided")
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="No hash found")
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items(), key=lambda x: x[0]))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if "user" in parsed:
        parsed["user"] = json.loads(unquote(parsed["user"]))
    return parsed
