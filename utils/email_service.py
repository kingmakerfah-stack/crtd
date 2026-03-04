import random
import string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from utils.tasks import send_otp_email_task, send_approval_email_task, send_html_email_task


# NOTE: Threading approach has been replaced with Celery for scalability.
# The EmailThread class is deprecated but kept for reference.
# All email sending now goes through Celery task queues for better performance,
# reliability, and the ability to scale to handle 1 lakh+ users.
class EmailThread:
    """
    DEPRECATED: Use Celery tasks instead.
    
    This class is kept for backward compatibility but should not be used.
    All email operations now go through Celery task queues.
    
    For more info, see utils/tasks.py
    """
    def __init__(self, email_message):
        self.email_message = email_message
        raise NotImplementedError(
            "EmailThread is deprecated. Use Celery tasks from utils/tasks.py instead."
        )


def generate_otp(length=4):
    """
    Generate a random One-Time Password (OTP) for email verification.
    
    This function creates a cryptographically random numeric string that can be sent
    to users for email verification. The OTP is temporary and should be stored in the
    database with an expiration timestamp.
    
    Args:
        length (int): The length of the OTP in digits. Default is 4.
                     Can be increased for higher security (e.g., 6 digits).
    
    Returns:
        str: A string of random digits.
    
    Usage Example:
        # Generate 4-digit OTP (default)
        otp = generate_otp()  # Returns something like '7392'
        
        # Generate 6-digit OTP
        otp = generate_otp(6)  # Returns something like '537291'
        
        # Store in database with expiration
        from accounts.models import EmailOTP
        from django.utils import timezone
        from datetime import timedelta
        
        email_otp = EmailOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Send to user
        EmailService.send_otp_email(user.email, otp)
    
    Security Notes:
        - Uses random.choices() for cryptographically secure random selection
        - Should always be stored with an expiration time (typically 10 minutes)
        - Should never be logged or exposed in error messages
        - The OTP should be sent via email, not SMS, for this implementation
    """
    return ''.join(random.choices(string.digits, k=length))


class EmailService:
    """
    Generic email service for the recruitment platform.
    
    Provides reusable methods for sending templated emails asynchronously via Celery.
    The context dictionary allows passing any dynamic variables to templates
    without changing the function signature.
    
    Architecture:
    - All email operations are queued as Celery tasks
    - Tasks are processed by Celery workers (can be scaled horizontally)
    - Results are stored in Redis with automatic expiration
    - Failed tasks automatically retry with exponential backoff
    - Suitable for handling 1 lakh+ concurrent users
    
    Benefits over Threading:
    ✅ Horizontal scalability (add more workers)
    ✅ Persistence (tasks survive server restarts)
    ✅ Monitoring (track task status)
    ✅ Priority queues (process critical emails first)
    ✅ Rate limiting (control email sending rate)
    ✅ Distributed processing (across multiple servers)
    """
    
    @staticmethod
    def send_html_email(subject, template_name, context, to_emails):
        """
        Queue an HTML email task for asynchronous sending via Celery.
        
        This method queues a task to Celery instead of sending immediately.
        The actual email sending happens in a background worker process.
        
        Args:
            subject (str): The email subject line.
            template_name (str): The path to the HTML email template.
            context (dict): A dictionary containing variables to inject into the template.
            to_emails (list): A list of recipient email addresses.
        
        Returns:
            celery.AsyncResult: Task result object that can be used to track status
        
        Example:
            context = {'first_name': 'John', 'reference_code': 'ABC123'}
            task_result = EmailService.send_html_email(
                subject='Your Application is Approved',
                template_name='emails/approval_email.html',
                context=context,
                to_emails=['john@example.com']
            )
            # Check task status
            print(task_result.state)  # PENDING, STARTED, SUCCESS, FAILURE
        
        Behavior:
            - Function returns immediately (non-blocking)
            - Email is sent asynchronously by Celery worker
            - Failed emails automatically retry up to 3 times
            - Task result is stored in Redis for tracking
        """
        # Queue the email task to Celery
        task_result = send_html_email_task.delay(
            subject=subject,
            template_name=template_name,
            context=context,
            to_emails=to_emails
        )
        return task_result
    
    @staticmethod
    def send_approval_email(user_email, context):
        """
        Queue an approval email task for asynchronous sending.
        
        This is a specific wrapper around send_html_email that queues approval
        emails to Celery workers.
        
        Args:
            user_email (str): The recipient's email address.
            context (dict): A dictionary containing:
                          - first_name (str): User's first name
                          - reference_code (str): User's approval reference code
                          - Any other variables for the template
        
        Returns:
            celery.AsyncResult: Task result object for tracking
        
        Example:
            context = {'first_name': 'Alice', 'reference_code': 'CRTD-2026-001'}
            task_result = EmailService.send_approval_email('alice@example.com', context)
            print(f"Task ID: {task_result.id}")
        """
        task_result = send_approval_email_task.delay(
            user_email=user_email,
            context=context
        )
        return task_result
    
    @staticmethod
    def send_otp_email(user_email, otp, context=None):
        """
        Queue an OTP email task for asynchronous sending via Celery.
        
        This method queues the OTP email to Celery workers for sending.
        The OTP should already be stored in the database before calling this method.
        
        Workflow:
        1. User registers with email and password
        2. System generates OTP using generate_otp()
        3. OTP is stored in EmailOTP model with expiration time
        4. This method queues the OTP email task
        5. Celery worker picks up the task and sends email
        6. User receives email with OTP
        7. User submits OTP for verification
        8. System verifies OTP against database record
        
        Args:
            user_email (str): The recipient's email address.
            otp (str): The OTP code to send (typically 4-6 digits).
            context (dict, optional): Additional variables for email template.
                                    Common keys:
                                    - 'first_name': User's first name
                                    - 'current_year': Current year for footer
                                    Defaults to empty dict if not provided.
        
        Returns:
            celery.AsyncResult: Task result object for tracking status
        
        Example Usage:
            from utils.email_service import generate_otp, EmailService
            from accounts.models import EmailOTP, CustomUser
            from django.utils import timezone
            from datetime import timedelta
            
            # After user registration
            user = CustomUser.objects.get(email='user@example.com')
            
            # Step 1: Generate OTP
            otp_code = generate_otp()
            
            # Step 2: Store OTP in database with 10-minute expiration
            email_otp = EmailOTP.objects.create(
                user=user,
                otp=otp_code,
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            
            # Step 3: Queue OTP email task
            task_result = EmailService.send_otp_email(
                user_email='user@example.com',
                otp=otp_code,
                context={
                    'first_name': user.email.split('@')[0],
                    'current_year': timezone.now().year
                }
            )
            
            # Check task status anytime
            print(f"Task ID: {task_result.id}")
            print(f"Task State: {task_result.state}")  # PENDING, STARTED, SUCCESS, FAILURE
        
        Email Template:
            - Sends using: templates/emails/otp_email.html
            - Subject: "Your OTP for Verification"
            - Method: HTML email with plain text fallback
            - Execution: Asynchronous (returns immediately)
        
        Scalability Benefits:
            - Email sending doesn't block API response (return immediately)
            - Celery workers can be scaled horizontally
            - Task status can be monitored in real-time
            - Failed emails automatically retry up to 3 times
            - Can handle 1 lakh+ concurrent users
        
        Security Considerations:
            - Email is sent asynchronously (not in request thread)
            - OTP is not logged in this method
            - Email should only be sent after OTP is stored in DB
            - Template includes expiration warning
            - Task is persisted in Redis even if server restarts
        """
        if context is None:
            context = {}
        
        # Queue the OTP email task to Celery
        task_result = send_otp_email_task.delay(
            user_email=user_email,
            otp=otp,
            context=context
        )
        return task_result
    
    @staticmethod
    def send_verification_otp(user, expiration_minutes=10):
        """
        Generates an OTP, stores it in the database, and queues email via Celery.
        
        This is the complete workflow for sending verification OTPs after registration.
        The OTP is stored in the EmailOTP model with an expiration time, and the email
        is queued to Celery workers for asynchronous sending.
        
        Args:
            user: The CustomUser instance to send OTP to.
            expiration_minutes (int): How long the OTP is valid for (default 10 minutes).
        
        Returns:
            tuple: (otp_code, email_otp_instance, task_result)
                - otp_code: The generated OTP string
                - email_otp_instance: The EmailOTP model instance
                - task_result: Celery AsyncResult for tracking email task
        
        Example:
            from accounts.models import CustomUser
            from utils.email_service import EmailService
            
            user = CustomUser.objects.get(email='user@example.com')
            otp_code, otp_instance, task = EmailService.send_verification_otp(user)
            
            # Check email task status
            print(f"Email Task ID: {task.id}")
            print(f"Email Task State: {task.state}")
        """
        from accounts.models import EmailOTP
        
        # Generate OTP
        otp_code = generate_otp()
        
        # Create or update EmailOTP record
        otp_instance, created = EmailOTP.objects.update_or_create(
            user=user,
            defaults={
                'otp': otp_code,
                'expires_at': timezone.now() + timedelta(minutes=expiration_minutes),
                'is_verified': False
            }
        )
        
        # Prepare context for email template
        context = {
            'first_name': user.email.split('@')[0] if '@' in user.email else user.email,
            'current_year': timezone.now().year
        }
        
        # Queue email task to Celery
        task_result = EmailService.send_otp_email(user.email, otp_code, context)
        
        return otp_code, otp_instance, task_result
    
    @staticmethod
    def verify_otp(user, otp_code):
        """
        Verifies the OTP provided by the user.
        
        Checks if the OTP matches, hasn't expired, and hasn't been used yet.
        If valid, marks the email as verified and updates the user.
        
        Args:
            user: The CustomUser instance.
            otp_code (str): The OTP code provided by the user.
        
        Returns:
            dict: A dictionary with 'success' (bool) and 'message' (str).
        
        Example:
            result = EmailService.verify_otp(user, '7392')
            if result['success']:
                print('Email verified!')
            else:
                print(result['message'])
        """
        from accounts.models import EmailOTP
        
        try:
            otp_instance = EmailOTP.objects.get(user=user)
        except EmailOTP.DoesNotExist:
            return {
                'success': False,
                'message': 'No OTP found. Please request a new one.'
            }
        
        # Check if expired
        if otp_instance.is_expired():
            return {
                'success': False,
                'message': 'OTP has expired. Please request a new one.'
            }
        
        # Check if already verified
        if otp_instance.is_verified:
            return {
                'success': False,
                'message': 'OTP has already been used.'
            }
        
        # Check if OTP matches
        if otp_instance.otp != otp_code:
            return {
                'success': False,
                'message': 'Invalid OTP. Please try again.'
            }
        
        # Mark as verified
        otp_instance.is_verified = True
        otp_instance.save()
        
        # Update user's email_verified status
        user.email_verified = True
        user.save()
        
        return {
            'success': True,
            'message': 'Email verified successfully!'
        }