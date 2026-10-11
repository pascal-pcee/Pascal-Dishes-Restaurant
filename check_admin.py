
from app import app, db, Customer

with app.app_context():
    email = input("Enter your administrator email: ").strip().lower()

    account = Customer.query.filter_by(email=email).first()

    if account is None:
        print("Account not found in the current database.")
    else:
        print("Name:", account.full_name)
        print("Email:", account.email)
        print("Administrator flag:", account.is_admin)
