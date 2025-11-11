import json
import hmac
import hashlib
import pytest
from django.urls import reverse
from django.conf import settings
from whatsapp_integration.models import WhatsAppWebhookEvent


@pytest.mark.django_db
class TestWebhookViews:

    def setup_method(self):
        self.client.defaults["CONTENT_TYPE"] = "application/json"

    def test_webhook_verification_success(self, client, settings):
        settings.WHATSAPP_VERIFY_TOKEN = "abc123"
        url = reverse("whatsapp-webhook-verify")
        resp = client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "abc123", "hub.challenge": "123"})
        assert resp.status_code == 200
        assert resp.content == b"123"

    def test_webhook_verification_fail(self, client, settings):
        settings.WHATSAPP_VERIFY_TOKEN = "abc123"
        url = reverse("whatsapp-webhook-verify")
        resp = client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "wrong"})
        assert resp.status_code == 403

    def test_receive_valid_payload_no_secret(self, client, settings):
        settings.WHATSAPP_APP_SECRET = None
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "1", "time": 12345, "changes": []}]}
        resp = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 202
        assert WhatsAppWebhookEvent.objects.count() == 1

    def test_receive_duplicate_event(self, client, settings):
        settings.WHATSAPP_APP_SECRET = None
        payload = {"entry": [{"id": "1"}]}
        WhatsAppWebhookEvent.objects.create(event_id="1", payload=payload)
        url = reverse("whatsapp-webhook-receive")
        resp = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"

    def test_missing_signature(self, client, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        url = reverse("whatsapp-webhook-receive")
        resp = client.post(url, data=json.dumps({"entry": []}), content_type="application/json")
        assert resp.status_code == 403

    def test_invalid_signature(self, client, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        url = reverse("whatsapp-webhook-receive")
        body = json.dumps({"entry": []}).encode()
        headers = {"HTTP_X_HUB_SIGNATURE_256": "sha256=invalid"}
        resp = client.post(url, body, **headers)
        assert resp.status_code == 403

    def test_valid_signature(self, client, settings):
        settings.WHATSAPP_APP_SECRET = "secret"
        url = reverse("whatsapp-webhook-receive")
        body = json.dumps({"entry": [{"id": "xyz"}]}).encode()
        sig = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        headers = {"HTTP_X_HUB_SIGNATURE_256": f"sha256={sig}"}
        resp = client.post(url, body, **headers)
        assert resp.status_code == 202

    def test_invalid_json_payload(self, client, settings):
        settings.WHATSAPP_APP_SECRET = None
        url = reverse("whatsapp-webhook-receive")
        resp = client.post(url, data="not-json", content_type="application/json")
        assert resp.status_code in (400, 415)

    def test_rate_limit_exceeded(self, mocker, client):
        mock_allow = mocker.patch("whatsapp_integration.views.RATE_LIMITER.allow", return_value=False)
        url = reverse("whatsapp-webhook-receive")
        resp = client.post(url, data=json.dumps({"entry": [{"id": "A"}]}), content_type="application/json")
        assert resp.status_code == 429
        mock_allow.assert_called_once()

    def test_event_id_generation(self, client):
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"time": 111}, {"time": 222}]}
        resp = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 202
        obj = WhatsAppWebhookEvent.objects.first()
        assert "|" in obj.event_id

    def test_event_dispatch_called(self, mocker, client):
        mock_dispatch = mocker.patch("whatsapp_integration.views.dispatch_event.delay")
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "xyz"}]}
        client.post(url, data=json.dumps(payload), content_type="application/json")
        mock_dispatch.assert_called_once()

    def test_webhook_idempotency(self, client):
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "123"}]}
        client.post(url, data=json.dumps(payload), content_type="application/json")
        resp2 = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert resp2.json()["status"] == "duplicate"

    def test_logging_on_invalid_signature(self, mocker, client, settings):
        settings.WHATSAPP_APP_SECRET = "s"
        mock_log = mocker.patch("whatsapp_integration.views.logger.warning")
        url = reverse("whatsapp-webhook-receive")
        body = json.dumps({"entry": []}).encode()
        client.post(url, body, HTTP_X_HUB_SIGNATURE_256="sha256=wrong")
        mock_log.assert_called_once()

    def test_payload_saved_correctly(self, client):
        url = reverse("whatsapp-webhook-receive")
        payload = {"entry": [{"id": "11"}]}
        client.post(url, data=json.dumps(payload), content_type="application/json")
        obj = WhatsAppWebhookEvent.objects.first()
        assert obj.payload["entry"][0]["id"] == "11"

    def test_multiple_valid_events(self, client):
        url = reverse("whatsapp-webhook-receive")
        for i in range(3):
            payload = {"entry": [{"id": str(i)}]}
            resp = client.post(url, data=json.dumps(payload), content_type="application/json")
            assert resp.status_code == 202
        assert WhatsAppWebhookEvent.objects.count() == 3
