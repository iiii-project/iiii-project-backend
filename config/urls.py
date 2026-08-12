from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/v1/auth/token/",
        TokenObtainPairView.as_view(permission_classes=[AllowAny]),
        name="token_obtain_pair",
    ),
    path(
        "api/v1/auth/token/refresh/",
        TokenRefreshView.as_view(permission_classes=[AllowAny]),
        name="token_refresh",
    ),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.fortunes.urls")),
    path("api/v1/", include("apps.divinations.urls")),
    path("api/v1/", include("apps.system.urls")),
    path("api/v1/", include("apps.speech.urls")),
    path("", include("apps.live2d.urls")),
]
