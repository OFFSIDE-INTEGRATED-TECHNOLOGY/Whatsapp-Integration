import logging
import time
import json
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter, Retry
from django.conf import settings
logger = logging.getLogger(__name__)

def exponential_backoff_sleep(attempt: int, base: float = 0.5, cap: float = 60.0) -> float:
    wait = min(cap, base * (2 ** (attempt - 1)))
    import random
    jitter = wait * 0.25
    return max(0.0, wait + random.uniform(-jitter, jitter))


class WhatsAppService:
    BASE_URL = "https://graph.facebook.com"

    def __init__(self, phone_number_id: Optional[str] = None, access_token: Optional[str] = None,
                 api_version: str = "v22.0", timeout: float = 10.0):
        self.phone_number_id = (phone_number_id or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")).strip()
        self.access_token = (access_token or getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")).strip()
        self.api_version = api_version
        self.timeout = timeout

        self.session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET', 'HEAD', 'OPTIONS', 'POST'])
        )
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.BASE_URL}/{self.api_version}/{self.phone_number_id}/{path.lstrip('/')}"

    def _post(self, path: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        url = self._url(path)
        headers = dict(self.headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        logger.debug("WhatsApp POST %s payload=%s", url, json.dumps(payload))
        resp = self.session.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def send_text(self, recipient: str, message: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": message},
        }
        return self._post("messages", payload, idempotency_key=idempotency_key)

    def send_template(self, recipient: str, template_name: str, language_code: str = "en_US",
                      components: Optional[List[dict]] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        return self._post("messages", payload, idempotency_key=idempotency_key)


default_whatsapp_service = WhatsAppService()
