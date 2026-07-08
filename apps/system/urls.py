from django.urls import path

from .views import HealthView, UsageStatsView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("admin/usage-stats/", UsageStatsView.as_view(), name="usage-stats"),
]
