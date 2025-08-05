import random
import datetime
from flask_mail import Message
from app.models import OTP, Account, db
from app import mail

def generate_otp():
    """Generate a secure 6-digit OTP as a string."""
    return str(random.randint(100000, 999999))

def send_otp(account_number=None, email=None, purpose="transaction", extra_info=None):
    if not email:
        # Fetch email from DB if not provided
        account = Account.query.filter_by(account_number=account_number).first()
        if not account or not account.email:
            return False
        email = account.email

    otp_code = generate_otp()

    # Store OTP in DB
    new_otp = OTP(
        account_number=account_number,
        otp_code=otp_code,
        purpose=purpose
    )
    db.session.add(new_otp)
    db.session.commit()

    # Compose the email
    subject = "Your OTP for Mini Banking System"
    body = f"""Dear Customer,

Your OTP is: {otp_code}
It is valid for 5 minutes."""

    # Add transaction details if available
    if extra_info:
        if purpose == "credit":
            body += (
                f"\n\n💰 Transaction Details:"
                f"\n• Account Number: {account_number}"
                f"\n• Amount to Credit: ₹{extra_info.get('amount')}"
            )
        elif purpose == "transfer":
            body += (
                f"\n\n🔄 Transaction Details:"
                f"\n• From Account: {account_number}"
                f"\n• To Account: {extra_info.get('to_account')}"
                f"\n• Amount: ₹{extra_info.get('amount')}"
            )
        elif purpose == "debit":
            body += (
                f"\n\n💸 Transaction Details:"
                f"\n• Account Number: {account_number}"
                f"\n• Amount to Debit: ₹{extra_info.get('amount')}"
            )

    body += "\n\nPlease do not share this OTP with anyone.\n\nThank you,\nMini Banking System"

    # Send the email
    msg = Message(subject, sender="no.reply.mini.bank.project@gmail.com", recipients=[email])
    msg.body = body

    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send OTP: {e}")
        return False

def verify_otp(account_number, submitted_otp, purpose):
    """
    Verify the OTP submitted by the user.
    """
    otp_record = OTP.query.filter_by(
        account_number=account_number,
        purpose=purpose
    ).order_by(OTP.created_at.desc()).first()

    if not otp_record:
        print("[VERIFY] No OTP found for this account and purpose.")
        return False

    # Check expiration or reuse
    if otp_record.is_expired():
        print("[VERIFY] OTP expired.")
        return False

    if otp_record.is_verified:
        print("[VERIFY] OTP already used.")
        return False

    if otp_record.otp_code != submitted_otp:
        print("[VERIFY] Invalid OTP.")
        return False

    # Mark OTP as used
    otp_record.is_verified = True
    db.session.commit()
    return True

