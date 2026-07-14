from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from urllib.parse import quote_plus
from uuid import uuid4

from django.conf import settings


ECPAY_STAGE_ACTION_URL = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
ECPAY_PROD_ACTION_URL = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5"


@dataclass
class EcPayCheckout:
    action_url: str
    params: dict[str, str]


def _build_check_mac_value(params: dict[str, str]) -> str:
    filtered = {key: value for key, value in params.items() if key != "CheckMacValue"}
    ordered = sorted(filtered.items(), key=lambda item: item[0].lower())
    query = "&".join(f"{key}={value}" for key, value in ordered)
    raw = f"HashKey={settings.ECPAY_HASH_KEY}&{query}&HashIV={settings.ECPAY_HASH_IV}"
    encoded = quote_plus(raw, safe="").lower()
    replacements = {
        "%2d": "-",
        "%5f": "_",
        "%2e": ".",
        "%21": "!",
        "%2a": "*",
        "%28": "(",
        "%29": ")",
    }
    for source, target in replacements.items():
        encoded = encoded.replace(source, target)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def create_ecpay_checkout(*, amount: int, choose_payment: str = "ALL") -> EcPayCheckout:
    order_id = f"donate{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:6]}"
    action_url = ECPAY_STAGE_ACTION_URL if settings.ECPAY_USE_STAGE else ECPAY_PROD_ACTION_URL
    params = {
        "MerchantID": settings.ECPAY_MERCHANT_ID,
        "MerchantTradeNo": order_id[:20],
        "MerchantTradeDate": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": str(amount),
        "TradeDesc": "AI temple oracle donation",
        "ItemName": f"AI temple oracle donation x 1 (NT${amount})",
        "ChoosePayment": choose_payment or "ALL",
        "EncryptType": "1",
        "ReturnURL": f"{settings.BACKEND_BASE_URL}/api/v1/donations/ecpay/notify/",
        "OrderResultURL": f"{settings.FRONTEND_BASE_URL}/donation",
        "ClientBackURL": f"{settings.FRONTEND_BASE_URL}/donation",
        "CustomField1": "temple-oracle",
        "Remark": "Created by Codex repair flow",
    }
    params["CheckMacValue"] = _build_check_mac_value(params)
    return EcPayCheckout(action_url=action_url, params=params)

