import hmac
import hashlib
import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from .models import WhatsAppWebhookEvent
from .serializers import WhatsAppWebhookEventSerializer
from .commands import dispatch_event
from .rate_limiter.token_bucket import RedisTokenBucketLimiter

logger = logging.getLogger(__name__)

VERIFY_TOKEN = getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
APP_SECRET = getattr(settings, "WHATSAPP_APP_SECRET", None)
RATE_LIMITER = RedisTokenBucketLimiter()


class WhatsAppWebhookVerifyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return Response(challenge, content_type="text/plain")

        return Response({"detail": "Invalid verification token"}, status=status.HTTP_403_FORBIDDEN)


class WhatsAppWebhookReceiveView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Redis rate limiting
        if not RATE_LIMITER.allow(key="whatsapp:webhook", max_tokens=10, rate_per_sec=1.5):
            logger.warning("Webhook rate limit exceeded.")
            return Response({"detail": "Rate limit exceeded"}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        raw_body = request.body
        if APP_SECRET:
            signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Hub-Signature")
            if not signature:
                return Response({"detail": "Missing signature"}, status=status.HTTP_403_FORBIDDEN)
            if signature.startswith("sha256="):
                signature = signature.split("sha256=")[1]
            expected = hmac.new(APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return Response({"detail": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        serializer = WhatsAppWebhookEventSerializer(data={"payload": request.data})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data["payload"] # type: ignore
        entry = payload.get("entry", [])
        event_id = "|".join([str(e.get("id") or e.get("time") or "") for e in entry]) or str(hash(str(payload)))

        obj, created = WhatsAppWebhookEvent.objects.get_or_create(event_id=event_id, defaults={"payload": payload})
        if not created:
            return Response({"status": "duplicate"}, status=status.HTTP_200_OK)

        dispatch_event.delay(str(obj.id)) # type: ignore
        return Response({"status": "accepted"}, status=status.HTTP_202_ACCEPTED)
