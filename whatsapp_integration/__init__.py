default_app_config = "whatsapp_integration.apps.WhatsAppIntegrationConfig"
__all__ = ["default_whatsapp_service"]
from .services.whatsapp_service import default_whatsapp_service

"""
Reusable Django WhatsApp integration.
This package provides webhook handling, Celery dispatching,
rate-limiting, and message abstractions.
"""

__version__ = "0.2.2"

# Do NOT import Django or settings-dependent modules at top-level.
# This prevents "ImproperlyConfigured" errors when users import the package outside Django.

def get_default_service():
    """
    Lazy getter for WhatsAppService so importing the package
    doesn’t require Django settings to be configured.
    """
    from .services.whatsapp_service import WhatsAppService
    return WhatsAppService()
# package init
