from rest_framework import serializers
from .models import EnquiryAnalytics, Testimonial

class EnquiryAnalyticsSerializer(serializers.Serializer):

    total_enquiry_received = serializers.IntegerField()
    enquiry_done = serializers.IntegerField()
    pending_enquiry = serializers.IntegerField()

class ReferenceCodeStatusSerializer(serializers.Serializer):

    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    whatsapp = serializers.CharField()
    reference_code = serializers.CharField()
    status = serializers.CharField()    

class EnquiryTableSerializer(serializers.ModelSerializer):

    full_name = serializers.SerializerMethodField()
    email = serializers.CharField(source="student.email")
    whatsapp = serializers.CharField(source="student.whatsapp_no")
    alternate_phone = serializers.CharField(source="student.alternate_phone")
    birthplace = serializers.CharField(source="student.birthplace_state")

    date_time = serializers.SerializerMethodField()

    class Meta:
        model = EnquiryAnalytics
        fields = [
            "id",
            "enquiry_token",
            "date_time",
            "full_name",
            "email",
            "whatsapp",
            "alternate_phone",
            "birthplace",
            "status"
        ]

    def get_full_name(self, obj):

        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_date_time(self, obj):

        return obj.created_at.strftime("%b %d, %Y at %I:%M%p").lower()
    
class UpdateReferenceStatusSerializer(serializers.Serializer):

    status = serializers.ChoiceField(
        choices=[
            "not_used",
            "account_created",
            "membership_pending",
            "membership_completed"
        ]
    )   

class TestimonialSerializer(serializers.ModelSerializer):

    class Meta:
        model = Testimonial
        fields = "__all__"