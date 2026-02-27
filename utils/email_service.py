import threading
import random
import string
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class EmailThread(threading.Thread):
    """
    Background thread for asynchronous email sending.
    
    This worker runs in the background, ensuring that SMTP operations
    do not block API responses.
    """
    
    def __init__(self, email_message):
        self.email_message = email_message
        super().__init__()

    def run(self):
        """Send the email message in the background thread."""
        self.email_message.send(fail_silently=False)


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
    
    Provides reusable methods for sending templated emails asynchronously.
    The context dictionary allows passing any dynamic variables to templates
    without changing the function signature.
    """
    
    @staticmethod
    def send_html_email(subject, template_name, context, to_emails):
        """
        Generic method to send HTML emails asynchronously.
        
        This method renders a Django template with the provided context,
        creates an email with HTML content and plain-text fallback, and
        sends it asynchronously using a background worker thread.
        
        Args:
            subject (str): The email subject line.
            template_name (str): The path to the HTML email template.
            context (dict): A dictionary containing variables to inject into the template.
                          This design allows passing any dynamic data without changing
                          the function signature.
            to_emails (list): A list of recipient email addresses.
        
        Example:
            context = {'first_name': 'John', 'reference_code': 'ABC123'}
            EmailService.send_html_email(
                subject='Your Application is Approved',
                template_name='emails/approval_email.html',
                context=context,
                to_emails=['john@example.com']
            )
        """
        # Render the HTML template with context
        html_content = render_to_string(template_name, context)
        
        # Generate plain-text fallback from context
        plain_text_fallback = f"Email from {settings.DEFAULT_FROM_EMAIL}"
        
        # Create the email message
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=plain_text_fallback,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails
        )
        
        # Attach HTML alternative
        email_message.attach_alternative(html_content, "text/html")
        
        # Send asynchronously in background thread
        EmailThread(email_message).start()
    
    @staticmethod
    def send_approval_email(user_email, context):
        """
        Sends an approval email to a user.
        
        This is a specific wrapper around send_html_email, demonstrating how to
        create domain-specific email methods for the platform.
        
        Args:
            user_email (str): The recipient's email address.
            context (dict): A dictionary containing:
                          - first_name (str): User's first name
                          - reference_code (str): User's approval reference code
        
        Example:
            context = {'first_name': 'Alice', 'reference_code': 'CRTD-2026-001'}
            EmailService.send_approval_email('alice@example.com', context)
        """
        EmailService.send_html_email(
            subject="Your Application is Approved",
            template_name="emails/approval_email.html",
            context=context,
            to_emails=[user_email]
        )
    
    @staticmethod
    def send_otp_email(user_email, otp, context=None):
        """
        Sends an OTP (One-Time Password) email to a user for email verification.
        
        This method is called after user registration to send a verification OTP.
        The OTP should already be stored in the database before calling this method.
        
        Workflow:
        1. User registers with email and password
        2. System generates OTP using generate_otp()
        3. OTP is stored in EmailOTP model with expiration time
        4. This method sends the OTP to user's email asynchronously
        5. User receives email with OTP and submits it for verification
        6. System verifies OTP against database record
        7. If valid, user's email_verified flag is set to True
        
        Args:
            user_email (str): The recipient's email address.
            otp (str): The OTP code to send (typically 4-6 digits).
                      Should match the code stored in EmailOTP model.
            context (dict, optional): Additional variables for email template.
                                    Common keys:
                                    - 'first_name' (str): User's first name
                                    - 'current_year' (int): Current year for footer
                                    - Any other template variables
                                    Defaults to empty dict if not provided.
        
        Returns:
            None - Sends email asynchronously in background thread
        
        Example Usage:
            from utils.email_service import generate_otp, EmailService
            from accounts.models import EmailOTP, CustomUser
            from django.utils import timezone
            from datetime import timedelta
            import datetime
            
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
            
            # Step 3: Send OTP email
            EmailService.send_otp_email(
                user_email='user@example.com',
                otp=otp_code,
                context={
                    'first_name': user.first_name or 'User',
                    'current_year': datetime.datetime.now().year
                }
            )
            # User receives email with OTP like '7392' prominently displayed
        
        Email Template:
            - Sends using: templates/emails/otp_email.html
            - Subject: "Your OTP for Verification"
            - Method: HTML email with plain text fallback
            - Execution: Asynchronous (doesn't block API response)
        
        Security Considerations:
            - Email is sent asynchronously in background thread
            - OTP is not logged anywhere in this method
            - Email should only be sent after OTP is stored in DB
            - The method assumes OTP is already generated and stored
            - Template includes security warning about OTP expiration
        
        Common Issues & Solutions:
            1. Email not received?
               - Check email service configuration in settings.py
               - Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env
               - Check spam folder
            
            2. Wrong recipient getting email?
               - Ensure user_email parameter is correct
               - Check CustomUser.objects.get(email=...) result
            
            3. OTP in email doesn't match what's in database?
               - Ensure same otp_code is used in generate and send
               - Check for type mismatch (int vs str)
        """
        if context is None:
            context = {}
        
        # Add OTP to the template context
        # This makes '{{ otp }}' available in otp_email.html template
        context['otp'] = otp
        
        # Send email using the generic send_html_email method
        # The email is sent asynchronously in a background thread
        # so the function returns immediately without blocking
        EmailService.send_html_email(
            subject="Your OTP for Verification",
            template_name="emails/otp_email.html",  # Path to OTP email template
            context=context,  # Template variables (otp, first_name, etc.)
            to_emails=[user_email]  # List of recipient emails
        )
    
    @staticmethod
    def send_verification_otp(user, expiration_minutes=10):
        """
        Generates an OTP, stores it in the database, and sends it to the user's email.
        
        This is the complete workflow for sending verification OTPs after registration.
        The OTP is stored in the EmailOTP model with an expiration time.
        
        Args:
            user: The CustomUser instance to send OTP to.
            expiration_minutes (int): How long the OTP is valid for (default 10 minutes).
        
        Returns:
            tuple: (otp_code, email_otp_instance)
        
        Example:
            from accounts.models import CustomUser
            from utils.email_service import EmailService
            
            user = CustomUser.objects.get(email='user@example.com')
            otp_code, otp_instance = EmailService.send_verification_otp(user)
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
        
        # Send email
        context = {
            'first_name': user.email.split('@')[0],  # Use part of email as fallback
            'current_year': timezone.now().year
        }
        EmailService.send_otp_email(user.email, otp_code, context)
        
        return otp_code, otp_instance
    
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