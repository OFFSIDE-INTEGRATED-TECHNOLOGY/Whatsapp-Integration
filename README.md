# Whatsapp Integration

**A reusable Django app providing enterprise-grade WhatsApp Business API integration with message queuing, Celery task orchestration, Redis-based rate limiting (Lua token bucket), idempotency, and webhook handling.**

Designed for **production environments** and **multi-project reusability**, this package provides a scalable way to send, track, and process WhatsApp messages across your Django applications.

---

## ✨ Features

- ✅ **Reusable Django app** – install once, integrate anywhere  
- 🚀 **Celery task orchestration** – background message processing with exponential backoff  
- 🧠 **Idempotency & retry safety** – prevents duplicate messages during failures  
- 🔐 **Secure webhook verification** – HMAC validation and token-based verification  
- 💬 **Unified service API** – `send_text` and `send_template` with optional components  
- 🧩 **Redis Lua rate limiter** – atomic token bucket algorithm for scalable throughput  
- ⚙️ **Configurable** – all keys & tokens loaded from Django `settings.py`  
- 🧱 **PostgreSQL-optimized schema** – indexed queries for performance  
- 🧰 **CI/CD & Docker ready** – comes with workflows, Dockerfile, and docker-compose  
- 📄 **PDF Generator Tool** – generate a full repo snapshot in a single PDF  

---

## 🧩 Architecture Overview

```bash

┌─────────────────────────────────────────────────────────────┐
│                      | Django App │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ whatsapp_integration                                    │ │
│ │ ├── models.py ← WhatsAppMessage, WebhookEvent           │ │
│ │ ├── services/ ← WhatsAppService abstraction             │ │
│ │ ├── tasks.py ← Celery async workers                     │ │
│ │ ├── rate_limiter/ ← Redis Lua token bucket              │ │
│ │ ├── views.py ← Webhook endpoints                        │ │
│ │ ├── commands.py ← Command + Event dispatcher            │ │
│ │ └── utils.py ← Error classification, helpers            │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

```
---

## 🛠 Installation

### 1️⃣ Install from PyPI (or locally)
```bash
pip install whatsapp_integration
```

### ⚙️ Configuration

- Add the app to your Django settings:
```bash
INSTALLED_APPS = [
    ...
    "whatsapp_integration",
]
```

- Environment Variables / Settings
```bash
WHATSAPP_PHONE_NUMBER_ID = "1234567890"
WHATSAPP_ACCESS_TOKEN = "your_long_lived_graph_api_token"
WHATSAPP_VERIFY_TOKEN = "your_webhook_verify_token"
WHATSAPP_APP_SECRET = "facebook_app_secret"   # optional but recommended
WHATSAPP_RATE_PER_SECOND = 1.5                # messages per second allowed
REDIS_URL = "redis://localhost:6379/0"
```

- Make migrations
```bash
python manage.py makemigrations
```


- Celery Setup

In your settings.py:
```bash
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```

Then in your project root:
```bash
celery -A your_project worker -l info
```

### 🔄 Sending Messages

Use the service directly or queue messages for asynchronous processing.

Example: Send text message immediately
```bash
from whatsapp_integration.services import whatsapp_service

whatsapp_service.default_whatsapp_service.send_text(
    recipient="15551234567",
    message="Hello from Django WhatsApp Integration!"
)
```

Example: Queue message for async send via Celery
```bash
from whatsapp_integration.models import WhatsAppMessage
from whatsapp_integration.tasks import send_whatsapp_message_task

msg = WhatsAppMessage.objects.create(
    recipient="15551234567",
    message_type="text",
    payload={"body": "Queued message test"}
)
send_whatsapp_message_task.delay(str(msg.id))
```

### 📬 Handling Webhooks

Facebook/WhatsApp will send inbound messages or delivery updates to your webhook.

##### URL Mapping

Add to your root urls.py:
```bash
urlpatterns = [
    ...
    path("api/v1/whatsapp/", include("whatsapp_integration.urls")),
]
```

This registers:
```bash
GET api/v1/whatsapp/webhook/verify/ → for verification handshake

POST api/v1/whatsapp/webhook/ → for inbound message events
```

Example verification response
```
GET api/v1/whatsapp/webhook/verify/?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=CHALLENGE
```

Returns CHALLENGE if token matches.

### 🚦 Rate Limiting (Lua + Redis)
How it works

A token bucket algorithm written in Lua ensures you never exceed Meta’s rate limits:

Each message consumes a “token”.

Tokens regenerate over time according to WHATSAPP_RATE_PER_SECOND.

Fully atomic via Redis EVALSHA (no race conditions).

Lua script: lua_token_bucket.lua

Settings
WHATSAPP_RATE_PER_SECOND = 1.0

### 🧠 Reliability & Idempotency

- Each message is stored with a unique idempotency_key

- Retries use the same key to avoid duplicate delivery

- Failed messages persist for visibility and can be retried manually

##### Celery Task Behavior
- Exponential backoff retry (2^n seconds)
- acks_late=True to avoid loss on worker crash
- Max 8 retries before marking message as failed

### 🔐 Webhook Security

- Optional HMAC verification (X-Hub-Signature-256)

- Prevents spoofed or replayed requests

- Use your Facebook App Secret for signing

### 🧩 Database Schema


#### WhatsAppMessage
| **Field**       | **Type**                                   | **Notes**                 |
| --------------- | ------------------------------------------ | ------------------------- |
| recipient       | `CharField`                                | phone number              |
| message_type    | `text` / `template`                        | message category          |
| payload         | `JSONField`                                | message body / components |
| status          | `queued` / `sent` / `failed` / `delivered` | lifecycle state           |
| idempotency_key | `UUID`                                     | prevents duplicates       |
| attempts        | `Integer`                                  | number of retries         |
| created_at      | `DateTime`                                 | timestamp                 |


#### WhatsAppWebhookEvent

| **Field** | **Type**    | **Description**           |
| --------- | ----------- | ------------------------- |
| event_id  | `CharField` | deduplication key         |
| payload   | `JSONField` | raw webhook payload       |
| processed | `Boolean`   | flag to avoid re-handling |

### Includes:

- Webhook verification test

- Event persistence test

(Extendable for rate limiter and Celery integration)

### 🧱 Deploying

Recommended environment:

- PostgreSQL

- Redis 7+

- Gunicorn with 2–4 workers

- Celery worker pool (concurrency >= 4)

- Nginx reverse proxy for SSL termination

Production tips:

- Use environment variables for tokens

- Rotate access tokens periodically

- Enable HTTPS and secure webhook secret

### 💡 Extending Functionality

- Add custom event handlers via register_handler in commands.py

- Extend rate limiter for per-tenant quotas

- Plug in Prometheus metrics to monitor message throughput

- Integrate with an internal analytics pipeline via Celery chains

### 🏗 Performance Best Practices

- Use persistent Redis connection pools (max_connections=100)

- Deploy Celery worker with concurrency matching CPU cores

- Shard messages across multiple phone numbers if exceeding rate limits

- Use DB connection pooling (e.g. pgBouncer)

- Enable GZIP compression on webhook endpoints for large payloads


### 📜 License

MIT License © 2025 OFFSIDE INTEGRATED TECHNOLOGY (Somtochukwu Emmanuel)

## 🤝 Contributing

Fork this repo

Create a feature branch
```bash
git checkout -b feature/awesome
```

Commit changes
```bash
git commit -m 'Add awesome feature'
```

Push branch and open a PR 🎉

### 📞 Support

For enterprise inquiries, please contact offsideint@gmail.com

For bugs, open an issue on GitHub.

Built with ❤️ by OFFSIDE INTEGRATED TECHNOLOGY — because WhatsApp deserves enterprise-grade Django integration.
