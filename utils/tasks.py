"""
Celery tasks for email service operations.

This module contains all asynchronous email tasks that are executed
by Celery workers. Tasks are queued and processed independently,
allowing the API to return responses immediately.

For scaling to 1 lakh users, these tasks are processed by multiple
Celery workers that can be scaled horizontally.
"""

try:
    from celery import shared_task
except ModuleNotFoundError:
    from utils.celery_compat import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, user_email, otp, context=None):
    try:
        if context is None:
            context = {}

        context['otp'] = otp
        html_content = render_to_string('emails/otp_email.html', context)
        plain_text = f"Your OTP: {otp}"

        email_message = EmailMultiAlternatives(
            subject="Your OTP for Verification",
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)

        logger.info(f"OTP email sent successfully to {user_email}")
        return {
            'status': 'success',
            'message': f'OTP email sent to {user_email}',
            'recipient': user_email,
        }
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {user_email}: {str(exc)}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True, max_retries=3)
def send_approval_email_task(self, user_email, context):
    try:
        html_content = render_to_string('emails/approval_email.html', context)
        plain_text = "Congratulations! Your application has been approved."

        email_message = EmailMultiAlternatives(
            subject="Your Application is Approved",
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)

        logger.info(f"Approval email sent successfully to {user_email}")
        return {
            'status': 'success',
            'message': f'Approval email sent to {user_email}',
            'recipient': user_email,
        }
    except Exception as exc:
        logger.error(f"Failed to send approval email to {user_email}: {str(exc)}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True, max_retries=3)
def send_html_email_task(self, subject, template_name, context, to_emails):
    try:
        html_content = render_to_string(template_name, context)
        plain_text = f"Email from {settings.DEFAULT_FROM_EMAIL}"

        email_message = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails,
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)

        logger.info(f"Email sent successfully to {', '.join(to_emails)} - Subject: {subject}")
        return {
            'status': 'success',
            'message': f'Email sent to {len(to_emails)} recipients',
            'recipients': to_emails,
            'subject': subject,
        }
    except Exception as exc:
        logger.error(f"Failed to send email to {to_emails}: {str(exc)}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task
def cleanup_expired_otps():
    from accounts.models import EmailOTP

    try:
        expired_otps = EmailOTP.objects.filter(expires_at__lt=timezone.now())
        count = expired_otps.count()
        expired_otps.delete()

        logger.info(f"Cleaned up {count} expired EmailOTP records")
        return {
            'status': 'success',
            'message': f'Cleaned {count} expired OTPs',
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as exc:
        logger.error(f"Failed to cleanup expired OTPs: {str(exc)}")
        return {
            'status': 'failed',
            'message': str(exc),
        }


@shared_task
def process_pending_emails():
    logger.info("Pending emails processing task executed")
    return {
        'status': 'success',
        'message': 'Pending emails processed',
        'timestamp': timezone.now().isoformat(),
    }


__all__ = [
    'send_otp_email_task',
    'send_approval_email_task',
    'send_html_email_task',
    'cleanup_expired_otps',
    'process_pending_emails',
]
