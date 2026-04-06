import random
import re
import string

from django.db import IntegrityError, transaction

from utils.email_service import EmailService

from .models import EnquiryTokenSequence, PreApplication, ReferalCode


ENQUIRY_TOKEN_PREFIX = "ENQ"
ENQUIRY_TOKEN_MAX_VALUE = 999999
ENQUIRY_TOKEN_PATTERN = re.compile(r"^ENQ(\d{6})$")


class ReferralGenerationError(Exception):
    pass


def format_enquiry_token(number):
    if number < 1 or number > ENQUIRY_TOKEN_MAX_VALUE:
        raise ValueError("Enquiry token sequence is out of range.")
    return f"{ENQUIRY_TOKEN_PREFIX}{number:06d}"


def extract_enquiry_token_number(token):
    match = ENQUIRY_TOKEN_PATTERN.match((token or "").strip().upper())
    return int(match.group(1)) if match else None


def _get_max_allocated_token_value():
    max_value = 0
    for token in PreApplication.objects.values_list("enquiry_token", flat=True):
        value = extract_enquiry_token_number(token)
        if value and value > max_value:
            max_value = value
    return max_value


def allocate_next_enquiry_token():
    with transaction.atomic():
        try:
            sequence = (
                EnquiryTokenSequence.objects.select_for_update()
                .get(pk=1)
            )
        except EnquiryTokenSequence.DoesNotExist:
            try:
                sequence = EnquiryTokenSequence.objects.create(
                    pk=1,
                    next_value=_get_max_allocated_token_value() + 1,
                )
            except IntegrityError:
                sequence = (
                    EnquiryTokenSequence.objects.select_for_update()
                    .get(pk=1)
                )

        if sequence.next_value > ENQUIRY_TOKEN_MAX_VALUE:
            raise ValueError("Enquiry token sequence limit reached.")

        token = format_enquiry_token(sequence.next_value)
        sequence.next_value += 1
        sequence.save(update_fields=["next_value"])
        return token


def generate_unique_referral_code(length=8):
    while True:
        code = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=length)
        )
        if not ReferalCode.objects.filter(code=code).exists():
            return code


def create_referral_for_pre_application(pre_application):
    if pre_application.is_deleted:
        raise ReferralGenerationError("Cannot generate referral for archived pre-application")

    if pre_application.verified or ReferalCode.objects.filter(student=pre_application).exists():
        raise ReferralGenerationError("Referral already exists for this student")

    with transaction.atomic():
        referral = ReferalCode.objects.create(
            student=pre_application,
            code=generate_unique_referral_code(),
        )
        pre_application.verified = True
        pre_application.save(update_fields=["verified"])

    context = {
        "first_name": pre_application.first_name,
        "reference_code": referral.code,
    }
    EmailService.send_approval_email(pre_application.email, context)
    return referral
