"""
Celery tasks for email service operations.

This module contains all asynchronous email tasks that are executed
by Celery workers. Tasks are queued and processed independently,
allowing the API to return responses immediately.

For scaling to 1 lakh users, these tasks are processed by multiple
Celery workers that can be scaled horizontally.

Usage:
    from utils.tasks import send_otp_email_task, send_approval_email_task
    
    # Queue a task (non-blocking)
    send_otp_email_task.delay('user@example.com', '1234')
    
    # Get task status
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    print(result.state)  # PENDING, STARTED, SUCCESS, FAILURE
"""

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, user_email, otp, context=None):
    """
    Asynchronous task to send OTP email.
    
    This task is executed by Celery workers, not in the request thread.
    If it fails, it will automatically retry up to 3 times with exponential backoff.
    
    Args:
        self: Task instance (for retries)
        user_email (str): Recipient email address
        otp (str): OTP code (typically 4-6 digits)
        context (dict, optional): Additional template variables
    
    Returns:
        dict: Task status with message
    
    Task Features:
        - Auto-retry on failure (max 3 retries)
        - Exponential backoff between retries
        - Detailed logging for debugging
        - Can be tracked using task ID
    
    Example:
        result = send_otp_email_task.delay('user@example.com', '1234')
        print(result.id)  # Task ID for tracking
    """
    try:
        if context is None:
            context = {}
        
        # Add OTP to context
        context['otp'] = otp
        
        # Render template
        html_content = render_to_string('emails/otp_email.html', context)
        plain_text = f"Your OTP: {otp}"
        
        # Create email message
        email_message = EmailMultiAlternatives(
            subject="Your OTP for Verification",
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email]
        )
        
        # Attach HTML content
        email_message.attach_alternative(html_content, "text/html")
        
        # Send email
        email_message.send(fail_silently=False)
        
        logger.info(f"OTP email sent successfully to {user_email}")
        
        return {
            'status': 'success',
            'message': f'OTP email sent to {user_email}',
            'recipient': user_email
        }
    
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {user_email}: {str(exc)}")
        
        # Retry with exponential backoff: 2^(retries_so_far) * 60 seconds
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True, max_retries=3)
def send_approval_email_task(self, user_email, context):
    """
    Asynchronous task to send approval email.
    
    This task sends personalized approval emails when students are approved.
    
    Args:
        self: Task instance (for retries)
        user_email (str): Recipient email address
        context (dict): Template variables including 'first_name', 'reference_code'
    
    Returns:
        dict: Task status with message
    
    Example:
        context = {
            'first_name': 'John',
            'reference_code': 'CRTD-2026-001'
        }
        result = send_approval_email_task.delay('john@example.com', context)
    """
    try:
        # Render template
        html_content = render_to_string('emails/approval_email.html', context)
        plain_text = f"Congratulations! Your application has been approved."
        
        # Create email message
        email_message = EmailMultiAlternatives(
            subject="Your Application is Approved",
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email]
        )
        
        # Attach HTML content
        email_message.attach_alternative(html_content, "text/html")
        
        # Send email
        email_message.send(fail_silently=False)
        
        logger.info(f"Approval email sent successfully to {user_email}")
        
        return {
            'status': 'success',
            'message': f'Approval email sent to {user_email}',
            'recipient': user_email
        }
    
    except Exception as exc:
        logger.error(f"Failed to send approval email to {user_email}: {str(exc)}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True, max_retries=3)
def send_html_email_task(self, subject, template_name, context, to_emails):
    """
    Generic asynchronous task to send HTML emails.
    
    This is a flexible method that can send any templated email.
    
    Args:
        self: Task instance (for retries)
        subject (str): Email subject
        template_name (str): Path to HTML template (e.g., 'emails/approval_email.html')
        context (dict): Template variables
        to_emails (list): List of recipient email addresses
    
    Returns:
        dict: Task status with message
    
    Example:
        context = {'first_name': 'Alice', 'token': 'abc123'}
        send_html_email_task.delay(
            subject='Email Verification',
            template_name='emails/verification_email.html',
            context=context,
            to_emails=['alice@example.com']
        )
    """
    try:
        # Render template
        html_content = render_to_string(template_name, context)
        plain_text = f"Email from {settings.DEFAULT_FROM_EMAIL}"
        
        # Create email message
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails
        )
        
        # Attach HTML content
        email_message.attach_alternative(html_content, "text/html")
        
        # Send email
        email_message.send(fail_silently=False)
        
        logger.info(f"Email sent successfully to {', '.join(to_emails)} - Subject: {subject}")
        
        return {
            'status': 'success',
            'message': f'Email sent to {len(to_emails)} recipients',
            'recipients': to_emails,
            'subject': subject
        }
    
    except Exception as exc:
        logger.error(f"Failed to send email to {to_emails}: {str(exc)}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task
def cleanup_expired_otps():
    """
    Periodic task to clean up expired OTPs.
    
    Runs hourly to delete OTP records that have expired (via Celery Beat).
    This keeps the database clean and removes unnecessary data.
    
    Returns:
        dict: Cleanup statistics
    
    Schedule:
        - Runs every hour (configured in celery.py beat_schedule)
    """
    from accounts.models import EmailOTP
    from django.utils import timezone
    
    try:
        # Find all expired OTPs
        expired_otps = EmailOTP.objects.filter(
            expires_at__lt=timezone.now()
        )
        
        count = expired_otps.count()
        expired_otps.delete()
        
        logger.info(f"Cleaned up {count} expired EmailOTP records")
        
        return {
            'status': 'success',
            'message': f'Cleaned {count} expired OTPs',
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as exc:
        logger.error(f"Failed to cleanup expired OTPs: {str(exc)}")
        return {
            'status': 'failed',
            'message': str(exc)
        }


@shared_task
def process_pending_emails():
    """
    Periodic task to process any pending emails.
    
    Runs every 5 minutes to handle emails that might have failed
    or are queued for sending.
    
    Returns:
        dict: Processing statistics
    
    Schedule:
        - Runs every 5 minutes (configured in celery.py beat_schedule)
    
    Note:
        This task can be extended to handle a queue/log of emails
        that need to be sent, providing additional reliability.
    """
    # This is a placeholder for future enhancement
    # Could be extended to handle email queues, retry failed emails, etc.
    
    logger.info("Pending emails processing task executed")
    
    return {
        'status': 'success',
        'message': 'Pending emails processed',
        'timestamp': timezone.now().isoformat()
    }
