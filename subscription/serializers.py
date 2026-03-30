from rest_framework import serializers

from .models import SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    discount = serializers.DecimalField(source='discount_percent', max_digits=5, decimal_places=2)
    final_price = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'description',
            'price',
            'duration_months',
            'duration',
            'discount',
            'currency',
            'final_price',
            'features',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'duration', 'final_price']

    def get_duration(self, obj):
        suffix = 'month' if obj.duration_months == 1 else 'months'
        return f'{obj.duration_months} {suffix}'

    def get_final_price(self, obj):
        return obj.final_price

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than 0.')
        return value

    def validate_duration_months(self, value):
        if value <= 0:
            raise serializers.ValidationError('Duration must be at least 1 month.')
        return value

    def validate_discount(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('Discount must be between 0 and 100.')
        return value

    def validate(self, attrs):
        if self.instance is None and SubscriptionPlan.objects.exists():
            raise serializers.ValidationError('Only one subscription plan can exist.')
        return attrs