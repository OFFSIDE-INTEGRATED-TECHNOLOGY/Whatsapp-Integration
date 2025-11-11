from celery import shared_task, Task
from django.db import transaction
import json
import logging
import time
from .models import WhatsAppMessage
from .services.whatsapp_service import default_whatsapp_service
from .rate_limiter.lua_wrapper import LuaRateLimiter
from .utils import classify_error

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6

# use LuaRateLimiter wrapper to call the Lua script atomically
rate_limiter = LuaRateLimiter.from_settings(prefix="whatsapp", rate_key="WHATSAPP_RATE_PER_SECOND")

@shared_task(bind=True, acks_late=True, max_retries=8)
def send_whatsapp_message_task(self, message_id: str):
    try:
        msg = WhatsAppMessage.objects.select_for_update().get(pk=message_id)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("WhatsApp message %s not found", message_id)
        return

    if msg.status in ("sent", "delivered") and msg.external_id:
        logger.info("Message %s already finalized", message_id)
        return

    # Rate limiting per phone number key (token bucket)
    key = f"{msg.recipient}"
    allowed = rate_limiter.consume(key, tokens=1.0)
    if not allowed:
        # requeue with exponential backoff
        msg.attempts += 1
        msg.status = "queued"
        msg.save(update_fields=["attempts", "status", "updated_at"])
        countdown = int(min(600, 2 ** msg.attempts))
        raise self.retry(countdown=countdown)

    # Ensure idempotency key
    if not msg.idempotency_key:
        msg.idempotency_key = f"wa-{msg.id}-{int(time.time())}"
        msg.save(update_fields=["idempotency_key"])

    try:
        msg.attempts += 1
        msg.status = "processing"
        msg.save(update_fields=["attempts", "status", "updated_at"])

        if msg.message_type == "text":
            body = msg.payload.get("body", "")
            resp = default_whatsapp_service.send_text(msg.recipient, body, idempotency_key=msg.idempotency_key)
        else:
            resp = default_whatsapp_service.send_template(
                msg.recipient,
                msg.template_name, # type: ignore
                language_code=msg.template_language or "en_US",
                components=msg.payload.get("components", []),
                idempotency_key=msg.idempotency_key,
            )

        # parse response
        external_id = None
        if isinstance(resp, dict):
            msgs = resp.get("messages")
            if isinstance(msgs, list) and msgs:
                external_id = msgs[0].get("id")
            else:
                external_id = resp.get("id") or json.dumps(resp)

        msg.external_id = external_id
        msg.status = "sent"
        msg.last_error = ""
        msg.save(update_fields=["external_id", "status", "last_error", "updated_at"])
        logger.info("Sent message %s recipient=%s external=%s", msg.id, msg.recipient, external_id)
    except Exception as exc:
        severity = classify_error(exc)
        msg.last_error = str(exc)[:4000]
        if severity == "transient" and msg.attempts < MAX_ATTEMPTS:
            msg.status = "queued"
            msg.save(update_fields=["status", "last_error", "attempts", "updated_at"])
            countdown = int(min(600, 2 ** msg.attempts))
            raise self.retry(countdown=countdown, exc=exc)
        else:
            msg.status = "failed"
            msg.save(update_fields=["status", "last_error", "updated_at"])
            logger.exception("Permanent failure sending message %s", msg.id)
            return
