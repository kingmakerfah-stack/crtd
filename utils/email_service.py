import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


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