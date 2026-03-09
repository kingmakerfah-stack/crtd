# Email Service Setup & Testing Guide

## Overview

The CRTD recruitment platform now includes a fully functional, asynchronous email service. This utility allows you to send templated HTML emails without blocking API responses.

## Architecture

### Components

1. **`utils/email_service.py`** - Generic email service with two main classes:
   - `EmailThread`: Background worker using Python threads for async sending
   - `EmailService`: Main service with generic and specific email methods

2. **`templates/emails/approval_email.html`** - Beautiful HTML template for approval emails

3. **Django Settings** - Configured with Neon PostgreSQL and email backends

## Key Features

✅ **Asynchronous Email Sending** - Uses threading to prevent API blocking  
✅ **Generic Base Method** - `send_html_email()` for any email type  
✅ **Template-Based** - Uses Django's `render_to_string` for dynamic content  
✅ **HTML + Plain Text** - `EmailMultiAlternatives` ensures compatibility  
✅ **Contextual Variables** - Pass any data via context dict without changing signatures  
✅ **Neon PostgreSQL** - Fully integrated with your database  

---

## Configuration

### Current Settings

**File:** `crtd/settings.py`

```python
# Email Backend (Development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Default sender email
DEFAULT_FROM_EMAIL = 'noreply@crtdplatform.com'
```

### For Production SMTP

To enable real email sending, update `crtd/settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # or your provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')  # Add to .env
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASS')  # Add to .env
```

Add to `.env`:
```
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-specific-password
```

---

## Usage

### Generic Email Method

Send any type of templated email:

```python
from utils.email_service import EmailService

context = {
    'first_name': 'John',
    'reference_code': 'ABC123',
    'custom_field': 'Any Value'
}

EmailService.send_html_email(
    subject='Custom Subject',
    template_name='emails/my_template.html',
    context=context,
    to_emails=['john@example.com', 'alice@example.com']
)
```

### Specific Approval Email

Send approval email with student data:

```python
from utils.email_service import EmailService

context = {
    'first_name': 'Alice',
    'reference_code': 'CRTD-2026-001'
}

EmailService.send_approval_email('alice@example.com', context)
```

### Integration with Pre-Application

The email service is automatically triggered when creating a referral code:

**Endpoint:** `POST /api/pre-application/referral/create/<student_id>/`

When successful, this automatically:
1. Creates a referral code
2. Marks student as verified
3. Sends approval email asynchronously

---

## Testing

### Quick Test with Management Command

```bash
# Test with default values
python manage.py test_email_service

# Test with custom email
python manage.py test_email_service --email your-email@example.com

# Test with custom data
python manage.py test_email_service \
    --email alice@example.com \
    --firstname "Alice Cooper" \
    --refcode "CRTD-2026-00123"
```

**Output:** Email will be printed to console (because we use `console.EmailBackend`)

### Manual Testing in Python Shell

```bash
python manage.py shell
```

```python
from utils.email_service import EmailService

# Send approval email
context = {
    'first_name': 'John',
    'reference_code': 'CRTD-2026-999'
}

EmailService.send_approval_email('john@example.com', context)

# Check console for email output
```

### API Testing with cURL

1. Create a pre-application:
```bash
curl -X POST http://localhost:8000/api/pre-application/submit-form/ \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "whatsapp_no": "9876543210",
    "birthplace_state": "Maharashtra",
    "qualification": "B.Tech",
    "specialization": "Computer Science",
    "college_name": "MIT",
    "college_state": "Maharashtra",
    "passing_year": "2024",
    "preferred_time": "10:00 AM"
  }'
```

2. Create referral (triggers email):
```bash
curl -X GET http://localhost:8000/api/pre-application/referral/create/1/
```

**Check console output for sent email!**

---

## Templates

### Creating New Email Templates

Create templates in `templates/emails/` directory:

**Template:** `templates/emails/rejection_email.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>Application Update</title>
</head>
<body>
    <h1>Hello {{ first_name }},</h1>
    <p>Thank you for your application.</p>
    <p>{{ message }}</p>
</body>
</html>
```

**Usage:**
```python
context = {
    'first_name': 'Bob',
    'message': 'We will contact you soon.'
}

EmailService.send_html_email(
    subject='Application Update',
    template_name='emails/rejection_email.html',
    context=context,
    to_emails=['bob@example.com']
)
```

---

## Context Dictionary Pattern

The key design pattern is using a `context` dictionary to pass any dynamic variables:

**Benefit:** You don't need to change function signatures when adding new template variables!

```python
# Today
context = {'first_name': 'John', 'reference_code': 'ABC123'}
EmailService.send_approval_email('john@example.com', context)

# Tomorrow - just add more fields to context
context = {
    'first_name': 'John',
    'reference_code': 'ABC123',
    'interview_date': '2026-03-15',
    'interview_time': '10:00 AM',
    'interview_link': 'https://meet.google.com/abc'
}
EmailService.send_approval_email('john@example.com', context)
```

---

## Troubleshooting

### Emails Not Showing?

With `console.EmailBackend`, emails are printed to console. Check:
```bash
# Terminal where Django server is running
# Look for something like:
# ------------------ Email Message from sender@example.com ------------------
# Subject: Your Application is Approved
# ...
```

### Template Not Found?

Make sure:
1. Template path is correct: `templates/emails/approval_email.html`
2. `TEMPLATES['DIRS']` includes `BASE_DIR / 'templates'` (already configured)
3. Template file exists and is readable

### Database Connection Error?

Verify `.env` file has valid `DATABASE_URL`:
```bash
DATABASE_URL=postgresql://...
```

Run migrations:
```bash
python manage.py migrate
```

---

## Database Structure

The integration works with these models:

**PreApplication** - Student application data
- first_name, last_name, email, etc.
- verified (Boolean) - Set to True when referral created

**ReferalCode** - Generated codes
- code (unique)
- student (FK to PreApplication)
- is_used (Boolean)

When referral is created → Email automatically sent to student

---

## Environment Variables

Required in `.env`:

```
# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://...

# Email (for production)
EMAIL_USER=your-email@example.com
EMAIL_PASS=your-app-specific-password
```

---

## File Structure

```
crtd-backend-v2/
├── crtd/
│   ├── settings.py          # Email + Database config
│   ├── urls.py              # Pre-application routes
│   └── ...
├── pre_application/
│   ├── views.py             # Email integration
│   ├── models.py
│   ├── serializers.py
│   ├── management/
│   │   └── commands/
│   │       └── test_email_service.py  # Test command
│   └── ...
├── templates/
│   └── emails/
│       └── approval_email.html  # Email template
├── utils/
│   ├── email_service.py     # Main email utility
│   └── ...
├── .env                     # Environment variables
└── manage.py
```

---

## Next Steps

1. **Test locally** using the management command
2. **Configure SMTP** for production emails
3. **Create more email templates** as needed
4. **Customize email templates** with your branding
5. **Add more wrapper methods** for different email types

---

## Support

For issues or questions about the email service:
- Check that `EMAIL_BACKEND` is correctly configured
- Verify template files exist
- Test with `python manage.py test_email_service`
- Check Django logs for errors

Happy emailing! 🚀
