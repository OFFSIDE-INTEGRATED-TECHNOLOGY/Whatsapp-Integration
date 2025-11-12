import json
import hmac
import hashlib
import pytest
from django.urls import reverse
from whatsapp_integration.models import WhatsAppWebhookEvent
from django.conf import settings

def generate_hmac_signature(payload):
    body = json.dumps(payload).encode()
    app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
    if app_secret:
        signature = hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        return {"HTTP_X_HUB_SIGNATURE_256": f"sha256={signature}"}
    return {}

@pytest.mark.django_db
class TestWebhookViews:
    """Comprehensive test suite for WhatsApp Webhook API."""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Inject the Django test client automatically for all tests."""
        self.client = client
        self.client.defaults["CONTENT_TYPE"] = "application/json"

    
    # -------------------------------
    # ✅ Verification endpoint tests
    # -------------------------------

    def test_webhook_verification_success(self, settings):
        settings.WHATSAPP_VERIFY_TOKEN = "abc123"
        url = reverse("whatsapp-webhook-verify")

        resp = self.client.get(
            url,
            {"hub.mode": "subscribe", "hub.verify_token": "abc123", "hub.challenge": "123"},
        )

        assert resp.status_code == 200
        assert resp.content == b"123"

    def test_webhook_verification_fail(self, settings):
        settings.WHATSAPP_VERIFY_TOKEN = "abc123"
        url = reverse("whatsapp-webhook-verify")

        resp = self.client.get(
            url, {"hub.mode": "subscribe", "hub.verify_token": "wrong"}
        )

        assert resp.status_code == 403

    # -------------------------------
    # ✅ Webhook receive tests
    # -------------------------------

    def test_receive_valid_payload_no_secret(self, settings):
        settings.WHATSAPP_APP_SECRET = None
        url = reverse("whatsapp-webhook-receive")

        payload = {"entry": [{"id": "1", "time": 12345, "changes": []}]}
        resp = self.client.post(url, data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 202
        assert WhatsAppWebhookEvent.objects.count() == 1

    def test_receive_duplicate_event(self, settings):
        settings.WHATSAPP_APP_SECRET = None
        payload = {"entry": [{"id": "1"}]}
        WhatsAppWebhookEvent.objects.create(event_id="1", payload=payload)
        url = reverse("whatsapp-webhook-receive")

        resp = self.client.post(url, data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"

    # -------------------------------
    # 🔐 Signature validation tests
    # -------------------------------
    def test_missing_signature(self, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        url = reverse("whatsapp-webhook-receive")
        resp = self.client.post(url, data=json.dumps({"entry": []}), content_type="application/json")
        assert resp.status_code == 403

    def test_invalid_signature(self, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        url = reverse("whatsapp-webhook-receive")
        body = {"entry": []}
        headers = {"HTTP_X_HUB_SIGNATURE_256": "sha256=invalid"}
        resp = self.client.post(url, data=json.dumps(body), content_type="application/json", **headers)
        assert resp.status_code == 403

    def test_valid_signature(self, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        url = reverse("whatsapp-webhook-receive")
        body = json.dumps({"entry": [{"id": "xyz"}]}).encode()
        sig = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        headers = {"HTTP_X_HUB_SIGNATURE_256": f"sha256={sig}"}
        resp = self.client.post(url, data=body, content_type="application/json", **headers)
        assert resp.status_code == 202

    # -------------------------------
    # 🧩 Edge cases
    # -------------------------------

    def test_invalid_json_payload(self, settings):
        settings.WHATSAPP_APP_SECRET = None
        url = reverse("whatsapp-webhook-receive")
        resp = self.client.post(url, data="not-json", content_type="application/json")
        assert resp.status_code in (400, 415)

    def test_rate_limit_exceeded(self, mocker):
        mock_allow = mocker.patch("whatsapp_integration.views.RATE_LIMITER.allow", return_value=False)
        url = reverse("whatsapp-webhook-receive")
        resp = self.client.post(url, data=json.dumps({"entry": [{"id": "A"}]}), content_type="application/json")
        assert resp.status_code == 429
        mock_allow.assert_called_once()

    def test_event_id_generation(self):
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"time": 111}, {"time": 222}]}
        body = json.dumps(payload).encode()
        # Calculate HMAC signature
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
        if app_secret:
            signature = hmac.new(
                app_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            headers = {"HTTP_X_HUB_SIGNATURE_256": f"sha256={signature}"}
        else:
            headers = {}
        resp = self.client.post(
            url,
            data=body,
            content_type="application/json",
            **headers
        )
        assert resp.status_code == 202
        obj = WhatsAppWebhookEvent.objects.first()
        assert "|" in obj.event_id

    def test_event_dispatch_called(self, mocker):
        mock_dispatch = mocker.patch("whatsapp_integration.views.dispatch_event.delay")
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "xyz"}]}
        body = json.dumps(payload).encode()
    
        # Calculate HMAC signature
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
        headers = {}
        if app_secret:
            signature = hmac.new(
                app_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            headers["HTTP_X_HUB_SIGNATURE_256"] = f"sha256={signature}"
    
        resp = self.client.post(
            url,
            data=body,
            content_type="application/json",
            **headers
        )
        assert resp.status_code == 202
        mock_dispatch.assert_called_once()

    def test_webhook_idempotency(self):
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "123"}]}
        body = json.dumps(payload).encode()

        # Calculate HMAC signature
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
        headers = {}
        if app_secret:
            signature = hmac.new(
                app_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            headers["HTTP_X_HUB_SIGNATURE_256"] = f"sha256={signature}"

        # First POST
        resp1 = self.client.post(
            url,
            data=body,
            content_type="application/json",
            **headers
        )
        assert resp1.status_code == 202

        # Second POST (should detect duplicate)
        resp2 = self.client.post(
            url,
            data=body,
            content_type="application/json",
            **headers
        )
        assert resp2.json()["status"] == "duplicate"

    def test_logging_on_invalid_signature(self, mocker, settings):
        settings.WHATSAPP_APP_SECRET = "s"
        mock_log = mocker.patch("whatsapp_integration.views.logger.warning")
        url = reverse("whatsapp-webhook-receive")
        body = json.dumps({"entry": []}).encode()
        resp = self.client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=wrong"
        )
        assert resp.status_code == 403
        mock_log.assert_called_once()

    def test_payload_saved_correctly(self):
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "11"}]}
        body = json.dumps(payload).encode()

        # Calculate HMAC signature
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
        headers = {}
        if app_secret:
            signature = hmac.new(
                app_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            headers["HTTP_X_HUB_SIGNATURE_256"] = f"sha256={signature}"

        resp = self.client.post(
            url,
            data=body,
            content_type="application/json",
            **headers
        )
        assert resp.status_code == 202
        obj = WhatsAppWebhookEvent.objects.first()
        assert obj.payload["entry"][0]["id"] == "11"


    def test_multiple_valid_events_status(self, mocker, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        mocker.patch("whatsapp_integration.views.RATE_LIMITER.allow", return_value=True)
        url = reverse("whatsapp-webhook-receive")
        for i in range(3):
            payload = {"entry": [{"id": str(i)}]}
            headers = generate_hmac_signature(payload)
            resp = self.client.post(
                url,
                data=json.dumps(payload).encode(),
                content_type="application/json",
                **headers
            )
            assert resp.status_code == 202

    def test_multiple_valid_events_database(self, mocker, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        mocker.patch("whatsapp_integration.views.RATE_LIMITER.allow", return_value=True)
        url = reverse("whatsapp-webhook-receive")
        for i in range(3):
            payload = {"entry": [{"id": str(i)}]}
            headers = generate_hmac_signature(payload)
            self.client.post(
                url,
                data=json.dumps(payload).encode(),
                content_type="application/json",
                **headers
            )
        assert WhatsAppWebhookEvent.objects.count() == 3