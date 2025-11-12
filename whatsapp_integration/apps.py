from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class WhatsAppIntegrationConfig(AppConfig):
    name = "whatsapp_integration"
    verbose_name = "WhatsApp Integration"

    def ready(self):
        """
        Called automatically when Django starts.
        Initialize default services here safely.
        """
        try:
            from .services.whatsapp_service import WhatsAppService

            # Create a default instance only if Django settings are configured
            from django.conf import settings
            if settings.configured:
                from . import services
                services.whatsapp_service.default_whatsapp_service = WhatsAppService()
                logger.info("✅ WhatsApp default service initialized successfully.")
            else:
                logger.warning("⚠️ Django settings not configured; skipping service init.")
        except Exception as e:
            logger.warning(f"⚠️ Skipping WhatsAppService initialization: {e}")
