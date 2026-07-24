from django.urls import path

from .views import FortuneBulkImportView, FortuneDetailView, FortuneSetListView

urlpatterns = [
    path("fortune-sets/", FortuneSetListView.as_view(), name="fortune-set-list"),
    path("fortune-sets/<str:fortune_set_code>/fortunes/<int:number>/", FortuneDetailView.as_view(), name="fortune-detail"),
    path("admin/fortune-sets/<str:fortune_set_code>/fortunes/import/", FortuneBulkImportView.as_view(), name="fortune-bulk-import"),
]
