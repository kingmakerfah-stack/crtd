from rest_framework import serializers
from .models import PaymentHistory


class PaymentHistorySerializer(serializers.ModelSerializer):
    customer_name=serializers.CharField(source='user.username',read_only=True)
    customer_email=serializers.EmailField(source='user.email',read_only=True)

    class Meta:
        model=PaymentHistory
        fields=[
            "transaction_id",
            "customer_name",
            "customer_email",
            "registration_date",
            "amount",
            "end_date",
            "payment_status",
            "payment_method",
            "payment_details",
            "membership_id",

        ]