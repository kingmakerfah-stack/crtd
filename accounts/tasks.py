"""
Celery tasks for accounts app.

This module contains account-related asynchronous tasks such as
OTP cleanup, email verification, and account maintenance.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_otps():
    """
    Periodic task to clean up expired OTPs from the database.
    
    This task runs hourly (via Celery Beat) and removes EmailOTP
    records that have expired. This keeps the database clean and
    removes unnecessary data that is no longer valid.
    
    Returns:
        dict: Cleanup statistics with status, message, and count
    
    Schedule:
        - Runs every hour (configured in celery.py beat_schedule)
    
    Logging:
        - Logs successful cleanup with count of deleted records
        - Logs any errors that occur during cleanup
    
    Database Impact:
        - Deletes all EmailOTP records where expires_at < current_time
        - Minimizes database bloat from expired OTPs
        - Should be run during off-peak hours if database is large
    
    Example:
        # This is automatically called by Celery Beat
        # But can also be called manually:
        from accounts.tasks import cleanup_expired_otps
        result = cleanup_expired_otps.delay()
    """
    from accounts.models import EmailOTP
    
    try:
        # Find all expired OTPs
        expired_count_before = EmailOTP.objects.filter(
            expires_at__lt=timezone.now()
        ).count()
        
        # Delete expired OTPs
        deleted_count, _ = EmailOTP.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        message = f'Successfully cleaned up {deleted_count} expired EmailOTP records'
        logger.info(message)
        
        return {
            'status': 'success',
            'message': message,
            'deleted_count': deleted_count,
            'timestamp': timezone.now().isoformat()
        }
    
    except Exception as exc:
        error_message = f'Failed to cleanup expired OTPs: {str(exc)}'
        logger.error(error_message, exc_info=True)
        
        return {
            'status': 'failed',
            'message': error_message,
            'timestamp': timezone.now().isoformat()
        }


@shared_task(bind=True, max_retries=3)
def send_email_verification(self, user_id):
    """
    Task to send email verification to a user.
    
    This task generates an OTP and sends verification email
    to a user's email address.
    
    Args:
        self: Task instance (for retries)
        user_id (int): The primary key of the CustomUser to verify
    
    Returns:
        dict: Status of the verification email operation
    
    Note:
        This is a more advanced task that could be used for
        custom email verification workflows beyond the standard OTP system.
    """
    from accounts.models import CustomUser
    from utils.email_service import EmailService
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        # Send verification OTP
        otp_code, otp_instance, email_task = EmailService.send_verification_otp(user)
        
        logger.info(f"Email verification task sent for user {user.email}")
        
        return {
            'status': 'success',
            'message': f'Verification email sent to {user.email}',
            'user_email': user.email,
            'otp_task_id': email_task.id if email_task else None
        }
    
    except CustomUser.DoesNotExist:
        error_message = f'User with id {user_id} not found'
        logger.error(error_message)
        
        return {
            'status': 'failed',
            'message': error_message
        }
    
    except Exception as exc:
        logger.error(f"Error in send_email_verification: {str(exc)}", exc_info=True)
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
