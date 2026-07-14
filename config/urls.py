from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.system.views import FrontendAppView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.fortunes.urls")),
    path("api/v1/", include("apps.divinations.urls")),
    path("api/v1/", include("apps.system.urls")),
    re_path(r"^(?!(api/|assets/)).*$", FrontendAppView.as_view(), name="frontend-app"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.FRONTEND_DIST_DIR / "assets")
