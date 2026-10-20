"""阿里云短信发送（RPC 签名 V1.0，零第三方依赖）。

复用 DailyCoach 已验证的 SendSms 实现，用于手机号验证码登录。
"""
import base64
import hashlib
import hmac
import json
import uuid
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from config import get_settings


def _percent_encode(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~")


def send_sms(phone: str, template_param: dict) -> dict:
    """发送短信，返回阿里云响应 dict（成功时 Code == "OK"）。"""
    settings = get_settings()
    params = {
        "AccessKeyId": settings.sms_access_key_id,
        "Action": "SendSms",
        "Format": "JSON",
        "PhoneNumbers": phone,
        "RegionId": "cn-hangzhou",
        "SignName": settings.sms_sign_name,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(uuid.uuid4()),
        "SignatureVersion": "1.0",
        "TemplateCode": settings.sms_template_code,
        "TemplateParam": json.dumps(template_param, ensure_ascii=False),
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Version": "2017-05-25",
    }
    canonical = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(params.items())
    )
    string_to_sign = "POST&%2F&" + _percent_encode(canonical)
    key = (settings.sms_access_key_secret + "&").encode("utf-8")
    signature = base64.b64encode(
        hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    params["Signature"] = signature
    query = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in params.items()
    )
    url = "https://dysmsapi.aliyuncs.com/?" + query
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))
