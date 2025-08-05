from flask_sqlalchemy import SQLAlchemy
import datetime
from sqlalchemy import LargeBinary

db = SQLAlchemy()

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100))
    dob = db.Column(db.Date, nullable=False)
    aadhar = db.Column(db.String(20), unique=True, nullable=False)
    pan = db.Column(db.String(20), unique=True)
    ifsc = db.Column(db.String(20), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(50), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    account_type = db.Column(db.String(50), nullable=False)
    pan_file = db.Column(LargeBinary)
    aadhar_file = db.Column(LargeBinary)
    photo = db.Column(LargeBinary)

class TransactionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10))  # credit, debit, transfer
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    remarks = db.Column(db.String(200))

    def __repr__(self):
        return f'<Transaction {self.account_number} - {self.type} ₹{self.amount}>'

class OTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    purpose = db.Column(db.String(20))  # credit / debit / transfer
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)

    def is_expired(self):
        return datetime.datetime.utcnow() > self.created_at + datetime.timedelta(minutes=5)
