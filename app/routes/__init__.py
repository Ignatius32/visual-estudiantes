# Package initialization file for routes
from app.routes.main import main
from app.routes.api import api_bp

__all__ = ['main', 'api_bp']