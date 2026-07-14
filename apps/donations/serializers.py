from rest_framework import serializers


class EcPayCheckoutSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1, max_value=1000000)
    choose_payment = serializers.CharField(required=False, default="ALL", max_length=20)

