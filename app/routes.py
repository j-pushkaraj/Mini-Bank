#  Standard Library Imports
import os
import uuid
import random
import datetime
import base64
import io
import mimetypes

#  Third-Party Library Imports
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, send_file, current_app,
    abort, send_from_directory, make_response
)
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
import magic

#  Internal App Imports
from app import db
from app.models import Account, TransactionHistory, OTP
from app.utils import send_otp, verify_otp




main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')


# This defines a route in Flask for the URL path "/login"
# It supports both GET (loading the form) and POST (submitting the form) requests
@main.route('/login', methods=['GET', 'POST'])
def login():
    # Check if the incoming request is a POST (i.e., form submitted)
    if request.method == 'POST':
        # Get the username and password values submitted through the form
        username = request.form['username']
        password = request.form['password']

        # Check if the credentials are exactly 'admin' for both username and password
        if username == 'admin' and password == 'admin':
            # Store a flag in session to indicate admin is logged in
            session['admin'] = True

            # Redirect the user to the dashboard page after successful login
            return redirect(url_for('main.dashboard'))
        else:
            # If login fails, flash a message with category 'danger' (used for styling like red alerts)
            flash('Invalid credentials. Try again.', 'danger')

    # If it's a GET request or login failed, render the login form again
    return render_template('login.html')



# This defines the route for '/logout'
@main.route('/logout')
def logout():
    # Clears all data stored in the current user session (logs the user out)
    session.clear()
    
    # Redirects the user to the login page after logging out
    return redirect(url_for('main.login'))




# This defines a route for the URL path '/dashboard'
@main.route('/dashboard')
def dashboard():
    # Check if the user is logged in as admin by verifying the session
    if not session.get('admin'):
        # If not logged in, redirect the user to the login page
        return redirect(url_for('main.login'))
    
    # If admin is logged in, render and show the dashboard HTML page
    return render_template('dashboard.html')




# Route to create a new account — supports both viewing the form (GET) and submitting the form (POST)
@main.route('/create-account', methods=['GET', 'POST'])
def create_account():
    # Check if the admin is logged in; if not, redirect to login
    if not session.get('admin'):
        return redirect(url_for('main.login'))

    # If form is submitted (POST request)
    if request.method == 'POST':
        try:
            # Get form data and uploaded files
            form = request.form
            files = request.files

            # Parse the date of birth from string to Python date format
            dob = datetime.datetime.strptime(form['dob'], "%Y-%m-%d").date()

            # Generate a unique account number with 'MINI' prefix
            account_number = "MINI" + str(uuid.uuid4().int)[:10]

            # ========== PHOTO STAMPING ==========
            photo_file = files.get('photo')  # Get the uploaded photo
            photo_blob = None  # Default to None if no photo

            if photo_file:
                # Open the image and convert to RGBA for transparency support
                img = Image.open(photo_file).convert("RGBA")
                
                # Create a transparent layer for stamping
                stamp = Image.new("RGBA", img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(stamp)

                # Determine font size based on image width
                font_size = int(img.width * 0.15)

                # Try loading a bold font; fallback to default if not available
                try:
                    font = ImageFont.truetype("arialbd.ttf", font_size)
                except:
                    font = ImageFont.load_default()

                # Text to stamp
                text = "MINI BANK"

                # Calculate text size for positioning
                if hasattr(draw, "textbbox"):  # Newer Pillow versions
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                else:  # Older Pillow versions
                    text_width, text_height = draw.textsize(text, font=font)

                # Centered position at the bottom of the image
                position = ((img.width - text_width) // 2, img.height - text_height - 10)

                # Draw the watermark text in red with some transparency
                draw.text(position, text, fill=(255, 0, 0, 180), font=font)

                # Combine original image and stamp layer
                stamped_img = Image.alpha_composite(img, stamp).convert("RGB")

                # Convert the final image to bytes (to store in DB)
                buf = io.BytesIO()
                stamped_img.save(buf, format="JPEG")
                photo_blob = buf.getvalue()

            # ========== CREATE ACCOUNT OBJECT ==========
            new_account = Account(
                account_number=account_number,
                first_name=form['first_name'],
                middle_name=form.get('middle_name'),
                last_name=form['last_name'],
                phone=form['phone'],
                gender=form['gender'],
                email=form.get('email'),
                dob=dob,
                aadhar=form['aadhar'],
                pan=form.get('pan'),
                ifsc=form['ifsc'],
                branch=form['branch'],
                city=form['city'],
                pincode=form['pincode'],
                address=form['address'],
                balance=float(form['balance']),
                account_type=form['account_type'],

                # Read binary files (PAN, Aadhar), if uploaded
                pan_file=files['pan_file'].read() if 'pan_file' in files else None,
                aadhar_file=files['aadhar_file'].read() if 'aadhar_file' in files else None,
                
                # Store the stamped photo blob
                photo=photo_blob
            )

            # Add the new account to the DB and save it
            db.session.add(new_account)
            db.session.commit()

            # ========== FLASH SUCCESS MESSAGE ==========
            flash(f"Account created successfully! Account Number: {account_number}", "success")

            # Flash an info message with a link to download the e-passbook
            flash(Markup(f'''
                <a href="{url_for('main.download_passbook', account_number=account_number)}"
                   class="btn btn-success mt-2">Download e-Passbook</a>
            '''), 'info')

            # Redirect back to the dashboard
            return redirect(url_for('main.dashboard'))

        # If any error occurs, show an error message
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    # For GET requests, show the account creation form
    return render_template('create_account.html')




# Route to update an account – allows GET (view page) and POST (search or update)
@main.route('/update-account', methods=['GET', 'POST'])
def update_account():
    # Ensure only logged-in admins can access this route
    if not session.get('admin'):
        return redirect(url_for('main.login'))

    # Default account is None (used to pass to the HTML template)
    account = None

    # If the form is submitted
    if request.method == 'POST':
        # CASE 1: Admin is searching for an account using account number
        if 'search' in request.form:
            account_number = request.form['account_number']
            
            # Query the database for matching account number
            account = Account.query.filter_by(account_number=account_number).first()
            
            # If not found, show an error message
            if not account:
                flash("Account not found.", "danger")

        # CASE 2: Admin is updating account details
        elif 'update' in request.form:
            # Get account by ID from hidden input field
            account_id = request.form['account_id']
            account = Account.query.get(account_id)

            if account:
                # Update account details from the form
                account.first_name = request.form['first_name']
                account.middle_name = request.form['middle_name']
                account.last_name = request.form['last_name']
                account.phone = request.form['phone']
                account.gender = request.form['gender']
                account.email = request.form['email']
                account.city = request.form['city']
                account.pincode = request.form['pincode']
                account.address = request.form['address']
                account.branch = request.form['branch']
                account.ifsc = request.form['ifsc']
                account.account_type = request.form['account_type']

                # Save changes to the database
                db.session.commit()
                flash("Account updated successfully!", "success")
            else:
                flash("Account not found for update.", "danger")

    # Render the update account form, with the account info (if found)
    return render_template('update_account.html', account=account)



# Route to view account details — supports both GET (to display form) and POST (to submit account number)
@main.route('/account-details', methods=['GET', 'POST'])
def account_details():
    # Only allow access if admin is logged in
    if not session.get('admin'):
        return redirect(url_for('main.login'))

    # Initialize variables for template rendering
    account = None
    transactions = []

    # If form is submitted
    if request.method == 'POST':
        # Get the entered account number from the form
        account_number = request.form['account_number']

        # Try to fetch the account from the database
        account = Account.query.filter_by(account_number=account_number).first()

        if not account:
            # If no matching account found, flash error
            flash("Account not found.", "danger")
        else:
            # ✅ If found, fetch transaction history for this account
            # Ordered by latest first (descending timestamp)
            transactions = TransactionHistory.query.filter_by(account_number=account_number)\
                                                   .order_by(TransactionHistory.timestamp.desc())\
                                                   .all()

    # Render the account details page with account info and transaction list (if available)
    return render_template('account_details.html', account=account, transactions=transactions)




# Route for admin to transfer funds between accounts
@main.route('/transfer', methods=['GET', 'POST'])
def transfer_funds():
    # Only allow access to logged-in admins
    if not session.get('admin'):
        return redirect(url_for('main.login'))

    #  If form is submitted
    if request.method == 'POST':
        # ----- PHASE 2: OTP SUBMISSION -----
        if 'otp_sent' in session and 'otp' in request.form:
            submitted_otp = request.form.get('otp')  # OTP entered by admin
            transfer_data = session.pop('transfer_data', {})  # Get and remove transfer info from session
            session.pop('otp_sent', None)  # Remove OTP flag from session

            # Check if all required data is present
            if not submitted_otp or not transfer_data:
                flash("All fields are required.", "warning")
                return redirect(url_for('main.transfer_funds'))

            # Verify if OTP is correct and valid
            if not verify_otp(transfer_data['from_account'], submitted_otp, 'transfer'):
                flash("Invalid or expired OTP.", "danger")
                return redirect(url_for('main.transfer_funds'))

            # OTP is correct → perform transaction
            from_account = Account.query.filter_by(account_number=transfer_data['from_account']).first()
            to_account = Account.query.filter_by(account_number=transfer_data['to_account']).first()

            amount = float(transfer_data['amount'])

            # Deduct from sender and add to receiver
            from_account.balance -= amount
            to_account.balance += amount

            # Record debit transaction
            db.session.add(TransactionHistory(
                account_number=from_account.account_number,
                type='debit',
                amount=amount,
                remarks=f'Transferred to {to_account.account_number}'
            ))

            # Record credit transaction
            db.session.add(TransactionHistory(
                account_number=to_account.account_number,
                type='credit',
                amount=amount,
                remarks=f'Received from {from_account.account_number}'
            ))

            # Save changes to the database
            db.session.commit()

            flash(f"₹{amount} transferred from {from_account.account_number} to {to_account.account_number}.", "success")
            return redirect(url_for('main.dashboard'))

        # ----- PHASE 1: Initial Form Submission -----
        else:
            # Read inputs from the form
            from_acc_no = request.form.get('from_account')
            to_acc_no = request.form.get('to_account')
            amount = request.form.get('amount')

            # Check for missing inputs
            if not from_acc_no or not to_acc_no or not amount:
                flash("All fields are required.", "warning")
                return redirect(url_for('main.transfer_funds'))

            # Validate amount format
            try:
                amount = float(amount)
            except ValueError:
                flash("Invalid amount format.", "warning")
                return redirect(url_for('main.transfer_funds'))

            # Prevent transferring to same account
            if from_acc_no == to_acc_no:
                flash("Source and destination accounts must be different.", "warning")
                return redirect(url_for('main.transfer_funds'))

            # Fetch both accounts from the database
            from_account = Account.query.filter_by(account_number=from_acc_no).first()
            to_account = Account.query.filter_by(account_number=to_acc_no).first()

            # Check if both accounts exist
            if not from_account or not to_account:
                flash("One or both accounts not found.", "danger")
                return redirect(url_for('main.transfer_funds'))

            # Check if source has enough balance
            if from_account.balance < amount:
                flash("Insufficient balance in source account.", "danger")
                return redirect(url_for('main.transfer_funds'))

            # ✅ Send OTP to the source account’s email (mocked or real)
            transfer_info = {
                'from_account': from_acc_no,
                'to_account': to_acc_no,
                'amount': amount
            }

            # If OTP successfully sent
            if send_otp(account_number=from_acc_no, purpose='transfer', extra_info=transfer_info):
                # Save OTP state and transfer data in session
                session['otp_sent'] = True
                session['transfer_data'] = transfer_info

                # Ask for OTP input
                flash("OTP sent to sender's email. Please enter the OTP to continue.", "info")
                return render_template('verify_otp.html', next_url=url_for('main.transfer_funds'))

            else:
                flash("Failed to send OTP email.", "danger")
                return redirect(url_for('main.transfer_funds'))

    # If GET request, show the transfer form
    return render_template('transfer.html')



# Route to credit money to an account — supports GET (form) and POST (form submission)
@main.route('/credit', methods=['GET', 'POST'])
def credit():
    # Only admins can access this functionality
    if not session.get('admin'):
        return redirect(url_for('main.login'))

    # If form is submitted
    if request.method == 'POST':

        #  Step 1: Initial credit request — send OTP
        if 'otp_sent' not in session:
            account_number = request.form.get('account_number')
            amount = request.form.get('amount')

            # Check for empty inputs
            if not account_number or not amount:
                flash("All fields are required.", "warning")
                return redirect(url_for('main.credit'))

            # Fetch the account from the database
            account = Account.query.filter_by(account_number=account_number).first()
            if not account:
                flash("Account not found.", "danger")
                return redirect(url_for('main.credit'))

            # Validate amount format
            try:
                amount = float(amount)
            except ValueError:
                flash("Invalid amount.", "warning")
                return redirect(url_for('main.credit'))

            # Store account and amount in session temporarily
            session['credit_data'] = {
                'account_number': account_number,
                'amount': amount
            }

            #  Send OTP for credit action
            if send_otp(account_number=account_number, purpose='credit', extra_info={'amount': amount}):
                session['otp_sent'] = True
                flash("OTP sent to registered email. Please verify to continue.", "info")
                return render_template('verify_otp.html', next_url=url_for('main.credit'))
            else:
                flash("Failed to send OTP.", "danger")
                return redirect(url_for('main.credit'))

        #  Step 2: OTP verification and credit operation
        elif 'otp_sent' in session and 'otp' in request.form:
            otp = request.form.get('otp')
            credit_data = session.pop('credit_data', None)  # Remove and retrieve credit info
            session.pop('otp_sent', None)  # Clear OTP flag

            # Check for missing data
            if not credit_data or not otp:
                flash("All fields are required.", "warning")
                return redirect(url_for('main.credit'))

            account_number = credit_data['account_number']
            amount = float(credit_data['amount'])

            # Verify OTP
            if not verify_otp(account_number, otp, purpose='credit'):
                flash("Invalid or expired OTP.", "danger")
                return redirect(url_for('main.credit'))

            # Fetch the account again to perform credit
            account = Account.query.filter_by(account_number=account_number).first()
            if not account:
                flash("Account not found.", "danger")
                return redirect(url_for('main.credit'))

            #  Update balance and log transaction
            account.balance += amount
            db.session.add(TransactionHistory(
                account_number=account_number,
                type='credit',
                amount=amount,
                remarks='Amount credited'
            ))
            db.session.commit()

            flash(f"₹{amount} credited to Account {account_number}.", "success")
            return redirect(url_for('main.dashboard'))

    # Default GET request — show credit form
    return render_template('credit.html')





# Route to perform a debit (withdrawal) from an account
@main.route('/debit', methods=['GET', 'POST'])
def debit():
    # Ensure only admin has access
    if not session.get('admin'):
        return redirect(url_for('main.login'))

    # If the form is submitted
    if request.method == 'POST':

        #  Phase 1: Admin submits account number & amount (OTP sending step)
        if 'otp_sent' not in session:
            account_number = request.form.get('account_number')
            amount = request.form.get('amount')

            # Validate inputs
            if not account_number or not amount:
                flash("All fields are required.", "warning")
                return redirect(url_for('main.debit'))

            # Ensure amount is numeric
            try:
                amount = float(amount)
            except ValueError:
                flash("Invalid amount.", "danger")
                return redirect(url_for('main.debit'))

            # Fetch the account from DB
            account = Account.query.filter_by(account_number=account_number).first()
            if not account:
                flash("Account not found.", "danger")
                return redirect(url_for('main.debit'))

            # Check if account has enough balance
            if account.balance < amount:
                flash("Insufficient balance in the account.", "danger")
                return redirect(url_for('main.debit'))

            #  Send OTP and store details in session
            if send_otp(account_number=account_number, purpose='debit', extra_info={'amount': amount}):
                session['otp_sent'] = True
                session['debit_data'] = {
                    'account_number': account_number,
                    'amount': amount
                }
                flash("OTP sent to customer's registered email.", "info")
                return render_template('verify_otp.html', next_url=url_for('main.debit'))
            else:
                flash("Failed to send OTP.", "danger")
                return redirect(url_for('main.debit'))

        #  Phase 2: Admin enters OTP (Verification + actual debit)
        else:
            submitted_otp = request.form.get('otp')
            if not submitted_otp:
                flash("OTP is required.", "warning")
                return redirect(url_for('main.debit'))

            # Retrieve and clear session data
            data = session.pop('debit_data', {})
            session.pop('otp_sent', None)

            account_number = data.get('account_number')
            amount = data.get('amount')

            # Validate session data
            if not account_number or not amount:
                flash("Something went wrong. Please try again.", "danger")
                return redirect(url_for('main.debit'))

            #  Verify OTP
            if not verify_otp(account_number, submitted_otp, purpose='debit'):
                flash("Invalid or expired OTP.", "danger")
                return redirect(url_for('main.debit'))

            # Proceed with debit
            account = Account.query.filter_by(account_number=account_number).first()
            if not account:
                flash("Account not found.", "danger")
                return redirect(url_for('main.debit'))

            # Final balance check (just to be safe)
            if account.balance < amount:
                flash("Insufficient balance.", "danger")
                return redirect(url_for('main.debit'))

            #  Update balance and log transaction
            account.balance -= amount
            db.session.add(TransactionHistory(
                account_number=account_number,
                type='debit',
                amount=amount,
                remarks='Amount debited'
            ))
            db.session.commit()

            flash(f"₹{amount} debited from account {account_number}.", "success")
            return redirect(url_for('main.dashboard'))

    # Default page load (GET) — show debit form
    return render_template('debit.html')





def generate_passbook_pdf(account):
    #  Set up the Jinja2 environment to load templates from 'app/templates'
    env = Environment(loader=FileSystemLoader('app/templates'))

    #  Load the HTML template for the passbook
    template = env.get_template('passbook.html')

    #  Convert the local photo path to a publicly accessible URL
    # Example: 'app/static/uploads/user.jpg' → 'uploads/user.jpg' → full URL via url_for
    photo_relative_path = account.photo.replace('app/static/', '')
    photo_url = url_for('static', filename=photo_relative_path, _external=True)

    #  Render the HTML by injecting account data and photo URL into the template
    html_out = template.render(account=account, photo_url=photo_url)

    #  Create an in-memory buffer to hold the PDF data
    from io import BytesIO
    pdf_io = BytesIO()

    #  Use WeasyPrint to convert rendered HTML into a PDF, using the app’s base URL for assets
    HTML(string=html_out, base_url=current_app.root_path).write_pdf(pdf_io)

    #  Move the cursor back to the start of the buffer so it can be read
    pdf_io.seek(0)

    #  Return the in-memory PDF file (can be returned in a Flask response)
    return pdf_io





#  Route to download the passbook PDF for a specific account
@main.route('/download-passbook/<account_number>')
def download_passbook(account_number):
    #  Fetch the account from the database; show 404 if not found
    account = Account.query.filter_by(account_number=account_number).first_or_404()

    #  Convert photo binary (BLOB) to base64-encoded string for embedding in HTML
    if account.photo:
        encoded_photo = base64.b64encode(account.photo).decode('utf-8')
        #  Format it as a data URI that HTML can use directly as the image source
        photo_url = f"data:image/jpeg;base64,{encoded_photo}"
    else:
        photo_url = None  # If no photo exists

    # Fetch all transactions for this account, newest first
    transactions = TransactionHistory.query.filter_by(account_number=account.account_number)\
                                           .order_by(TransactionHistory.timestamp.desc())\
                                           .all()

    #  Render the passbook.html with account details, photo, and transaction history
    html = render_template('passbook.html', account=account, photo_url=photo_url, transactions=transactions)

    #  Convert the HTML to a PDF using WeasyPrint (no need for base_url since no external file used)
    pdf_bytes = HTML(string=html).write_pdf()

    #  Return PDF as downloadable response
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=passbook_{account.account_number}.pdf'
    return response




#  Route to view/download Aadhar file based on account ID
@main.route('/view-aadhar/<int:account_id>')
def view_aadhar(account_id):
    # Fetch the account from the DB, 404 if not found
    account = Account.query.get_or_404(account_id)

    # If Aadhar file is present
    if account.aadhar_file:
        # Detect the MIME type of the binary content (e.g., image/png or application/pdf)
        mime = magic.Magic(mime=True).from_buffer(account.aadhar_file)

        # Send the binary data as a file response
        return send_file(
            io.BytesIO(account.aadhar_file),    # Create a readable stream from bytes
            mimetype=mime,                      # Set correct MIME type
            download_name='aadhar_file'         # Name of the downloaded file
        )

    # If no Aadhar file is available
    return "No Aadhar file", 404




#  Route to view/download PAN file based on account ID
@main.route('/view-pan/<int:account_id>')
def view_pan(account_id):
    # Fetch the account from the database; return 404 if ID is invalid
    account = Account.query.get_or_404(account_id)

    # Check if PAN file exists in the account record
    if account.pan_file:
        #  Dynamically detect MIME type (e.g., application/pdf, image/jpeg, etc.)
        mime = magic.Magic(mime=True).from_buffer(account.pan_file)

        #  Send the PAN file as an inline or downloadable response
        return send_file(
            io.BytesIO(account.pan_file),  # Converts binary BLOB to a readable stream
            mimetype=mime,                 # Applies correct content type
            download_name='pan_file'       # Sets the download filename
        )

    #  If no PAN file is present, return 404 error
    return "No PAN file", 404




#  Route to view the photo of an account holder by account ID
@main.route('/view-photo/<int:account_id>')
def view_photo(account_id):
    #  Fetch the account from the database or return 404 if not found
    account = Account.query.get_or_404(account_id)

    #  If photo is available
    if account.photo:
        #  Send the photo as a response (JPEG format assumed)
        return send_file(
            io.BytesIO(account.photo),  # Convert binary BLOB to stream
            mimetype='image/jpeg'       # Set MIME type to image
        )

    # If no photo exists
    return "No Photo found", 404

