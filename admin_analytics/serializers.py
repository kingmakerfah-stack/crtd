from rest_framework import serializers


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