from routers.auth import router as auth_router
from routers.documents import router as documents_router
from routers.chat import router as chat_router
from routers.calls import router as calls_router
from routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "documents_router",
    "chat_router",
    "calls_router",
    "admin_router",
]
