from rest_framework import serializers
from accounts.models import CustomUser
from admin_panel.models import AdminUser


class AdminRegisterSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=AdminUser.ROLE_CHOICES)

    def create(self, validated_data):

        email = validated_data["email"]
        password = validated_data["password"]
        name = validated_data["name"]
        role = validated_data["role"]

        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            role="admin"
        )

        admin = AdminUser.objects.create(
            user=user,
            name=name,
            role=role
        )

        return admin