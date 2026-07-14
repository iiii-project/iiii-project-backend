from django.urls import path

from .views import EcPayCheckoutView, EcPayNotifyView


urlpatterns = [
    path("donations/ecpay/", EcPayCheckoutView.as_view(), name="donations-ecpay-checkout"),
    path("donations/ecpay/notify/", EcPayNotifyView.as_view(), name="donations-ecpay-notify"),
]
