import logging
import smtplib

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def send_booking_email(booking, subject, message):
    recipient = booking.customer_email or booking.user.email
    if not recipient:
        logger.warning(
            "Booking %s email was not sent: no customer email.",
            booking.pk,
        )
        return
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except (smtplib.SMTPException, OSError):
        logger.exception("Unable to send email for booking %s.", booking.pk)
