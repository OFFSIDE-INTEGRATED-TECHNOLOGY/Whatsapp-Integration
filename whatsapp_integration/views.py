import hmac
import hashlib
import logging
from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.utils.encoding import force_bytes
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import WhatsAppWebhookEvent
from .serializers import WhatsAppWebhookEventSerializer
from .commands import dispatch_event
try:
    from .rate_limiter.token_bucket import RedisTokenBucketLimiter
except ImportError:
    RedisTokenBucketLimiter = None

logger = logging.getLogger(__name__)
RATE_LIMITER = RedisTokenBucketLimiter() if RedisTokenBucketLimiter else None

# --------------------------------------------------------------------
# 🔐 Webhook Verification (GET)
# --------------------------------------------------------------------
class WhatsAppWebhookVerifyView(APIView):
    """Responds to Meta’s webhook verification challenge."""
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            return HttpResponse(challenge, content_type="text/plain")

        logger.warning("Invalid webhook verification attempt.")
        return Response(
            {"detail": "Invalid verification token"},
            status=status.HTTP_403_FORBIDDEN,
        )
# --------------------------------------------------------------------
# 📬 Webhook Receiver (POST)
# --------------------------------------------------------------------
class WhatsAppWebhookReceiveView(APIView):
    """Handles incoming webhook events with HMAC + rate limit."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)

        # ✅ Rate limiting
        if RATE_LIMITER:
            RATE_LIMITER.redis.delete("whatsapp:webhook")
            allowed = RATE_LIMITER.allow(
                key="whatsapp:webhook",
                max_tokens=10,
                rate_per_sec=getattr(settings, "WHATSAPP_RATE_PER_SECOND", 1.5),
            )
            if not allowed:
                return Response(
                    {"detail": "Rate limit exceeded"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        raw_body = request.body

        # ✅ Conditional HMAC signature check
        if app_secret:
            signature = (
                request.META.get("HTTP_X_HUB_SIGNATURE_256")
                or request.META.get("HTTP_X_HUB_SIGNATURE")
            )
            if not signature:
                logger.warning("Missing signature header.")
                return HttpResponseForbidden("Missing signature")

            if signature.startswith("sha256="):
                provided_sig = signature.split("sha256=")[1]
                expected_sig = hmac.new(
                    app_secret.encode(), force_bytes(raw_body), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(provided_sig, expected_sig):
                    logger.warning("Invalid signature.")
                    return HttpResponseForbidden("Invalid signature")

        # ✅ Validate and persist
        serializer = WhatsAppWebhookEventSerializer(data={"payload": request.data})
        if not serializer.is_valid():
            logger.warning("Invalid webhook payload: %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data["payload"]
        entry = payload.get("entry", [])
        event_id = "|".join(
            [str(e.get("id") or e.get("time") or "") for e in entry]
        ) or str(hash(str(payload)))

        obj, created = WhatsAppWebhookEvent.objects.get_or_create(
            event_id=event_id, defaults={"payload": payload}
        )

        if not created:
            return Response({"status": "duplicate"}, status=status.HTTP_200_OK)

        dispatch_event.delay(str(obj.id))
        logger.info("Webhook event accepted: %s", event_id)
        return Response({"status": "accepted"}, status=status.HTTP_202_ACCEPTED)
