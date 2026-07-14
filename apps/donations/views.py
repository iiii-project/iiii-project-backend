from rest_framework.response import Response
from rest_framework.views import APIView

from config.utils import ok

from .serializers import EcPayCheckoutSerializer
from .services import create_ecpay_checkout


class EcPayCheckoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = EcPayCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkout = create_ecpay_checkout(**serializer.validated_data)
        return Response(
            ok(
                {
                    "action_url": checkout.action_url,
                    "params": checkout.params,
                }
            )
        )


class EcPayNotifyView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        return Response("1|OK")

