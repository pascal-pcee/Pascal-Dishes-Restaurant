
from sqlalchemy import inspect, text
from app import app, db, Customer

with app.app_context():
    inspector = inspect(db.engine)

    if "customer" not in inspector.get_table_names():
        print("Customer table not found. Check your database.")
    else:
        columns = [
            column["name"]
            for column in inspector.get_columns("customer")
        ]

        if "is_admin" not in columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE customer "
                        "ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            print("Database updated successfully.")
        else:
            print("The is_admin column already exists.")

    db.create_all()
    print("Database check completed.")
