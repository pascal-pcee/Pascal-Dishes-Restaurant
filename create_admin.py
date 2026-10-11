
from getpass import getpass
from sqlalchemy import select
from app import app, db, Customer

with app.app_context():
    print("=== Pascal Dishes Restaurant: Admin Setup ===")

    name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip().lower()

    if not name or not email or "@" not in email:
        print("Please enter a name and a valid email address.")
    else:
        existing = db.session.execute(
            select(Customer).where(Customer.email == email)
        ).scalar_one_or_none()

        if existing and existing.is_admin:
            print("This account is already an administrator.")
        else:
            password = getpass("Create administrator password (8+ characters): ")
            confirm = getpass("Confirm administrator password: ")

            if len(password) < 8:
                print("Password must be at least 8 characters.")
            elif password != confirm:
                print("Passwords do not match.")
            else:
                if existing:
                    admin = existing
                    print("Using the existing customer account.")
                else:
                    admin = Customer(full_name=name, email=email)
                    db.session.add(admin)

                admin.set_password(password)
                admin.is_admin = True
                db.session.commit()

                print("Administrator account created successfully!")
                print("Email:", email)
