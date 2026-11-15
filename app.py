
import os
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import (
    Flask, flash, redirect, render_template,
    request, session, url_for
)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "local-demo-key-change-me"
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:capital123@db:5432/capitalone"
)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)


def get_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return decorated_function


def initialize_database():
    """Create applications table and synthetic demo records."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id SERIAL PRIMARY KEY,
                    application_ref VARCHAR(24) UNIQUE NOT NULL,
                    full_name VARCHAR(120) NOT NULL,
                    email VARCHAR(160) NOT NULL,
                    phone VARCHAR(30) NOT NULL,
                    employment_type VARCHAR(40) NOT NULL,
                    annual_income NUMERIC(12,2) NOT NULL,
                    requested_credit_limit NUMERIC(12,2) NOT NULL,
                    card_type VARCHAR(60) NOT NULL,
                    housing_status VARCHAR(40) NOT NULL,
                    application_status VARCHAR(40) NOT NULL DEFAULT 'Received',
                    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                SELECT COUNT(*) AS total
                FROM applications
                WHERE is_demo = TRUE
            """)

            if cur.fetchone()["total"] == 0:
                demo_rows = [
                    ("Aarav Mehta", "aarav.mehta@example.com",
                     "+1-202-555-0101", "Salaried", 82000, 12000,
                     "Quicksilver Cash Rewards", "Rent", "Under Review"),

                    ("Sophia Carter", "sophia.carter@example.com",
                     "+1-202-555-0102", "Self-employed", 96000, 18000,
                     "Savor Cash Rewards", "Own", "Received"),

                    ("Noah Williams", "noah.williams@example.com",
                     "+1-202-555-0103", "Salaried", 68000, 8000,
                     "Platinum Mastercard", "Rent", "Documents Pending"),

                    ("Olivia Brown", "olivia.brown@example.com",
                     "+1-202-555-0104", "Student", 24000, 2000,
                     "Platinum Mastercard", "With Family", "Received"),
                ]

                for row in demo_rows:
                    ref = (
                        "CO-"
                        + datetime.utcnow().strftime("%y%m%d")
                        + "-"
                        + secrets.token_hex(2).upper()
                    )

                    cur.execute("""
                        INSERT INTO applications (
                            application_ref, full_name, email, phone,
                            employment_type, annual_income,
                            requested_credit_limit, card_type,
                            housing_status, application_status, is_demo
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                        ON CONFLICT (application_ref) DO NOTHING
                    """, (ref, *row))

        conn.commit()


def fetch_metrics():
    """Return aggregate figures only, not individual applications."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE application_status = 'Received'
                    ) AS received,
                    COUNT(*) FILTER (
                        WHERE application_status = 'Under Review'
                    ) AS under_review,
                    COALESCE(
                        AVG(requested_credit_limit), 0
                    ) AS avg_limit
                FROM applications
            """)
            return cur.fetchone()


def fetch_applications():
    """Fetch individual records for the protected admin dashboard."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM applications
                ORDER BY created_at DESC, id DESC
            """)
            return cur.fetchall()


@app.route("/")
def index():
    metrics = fetch_metrics()
    return render_template("index.html", metrics=metrics)


@app.route("/apply", methods=["POST"])
def apply():
    fields = {
        "full_name": request.form.get("full_name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "employment_type": request.form.get("employment_type", "").strip(),
        "annual_income": request.form.get("annual_income", "").strip(),
        "requested_credit_limit": request.form.get(
            "requested_credit_limit", ""
        ).strip(),
        "card_type": request.form.get("card_type", "").strip(),
        "housing_status": request.form.get("housing_status", "").strip(),
    }

    if not all(fields.values()):
        flash("Please complete every field before submitting.", "error")
        return redirect(url_for("index") + "#new-application")

    if "@" not in fields["email"] or "." not in fields["email"].split("@")[-1]:
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("index") + "#new-application")

    try:
        income = Decimal(fields["annual_income"])
        credit_limit = Decimal(fields["requested_credit_limit"])

        if (
            not income.is_finite()
            or not credit_limit.is_finite()
            or income <= 0
            or credit_limit <= 0
            or income > Decimal("100000000")
            or credit_limit > Decimal("10000000")
        ):
            raise InvalidOperation

    except (InvalidOperation, ValueError):
        flash(
            "Enter valid positive amounts for annual income "
            "and requested credit limit.",
            "error"
        )
        return redirect(url_for("index") + "#new-application")

    ref = (
        "CO-"
        + datetime.utcnow().strftime("%y%m%d")
        + "-"
        + secrets.token_hex(3).upper()
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO applications (
                    application_ref, full_name, email, phone,
                    employment_type, annual_income,
                    requested_credit_limit, card_type,
                    housing_status, application_status, is_demo
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Received',FALSE)
            """, (
                ref,
                fields["full_name"],
                fields["email"],
                fields["phone"],
                fields["employment_type"],
                income,
                credit_limit,
                fields["card_type"],
                fields["housing_status"]
            ))

        conn.commit()

    flash(
        f"Demo application {ref} was submitted successfully.",
        "success"
    )
    return redirect(url_for("index"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")

        if not ADMIN_PASSWORD:
            flash("Admin password is not configured.", "error")
        elif secrets.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Incorrect password. Please try again.", "error")

    return render_template("admin_login.html")


@app.route("/admin")
@login_required
def admin_dashboard():
    applications = fetch_applications()
    metrics = fetch_metrics()

    return render_template(
        "admin.html",
        applications=applications,
        metrics=metrics
    )


@app.route("/admin/logout", methods=["POST"])
@login_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/health")
def health():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")

        return {"status": "ok", "database": "connected"}, 200

    except Exception:
        app.logger.exception("Database health check failed")
        return {"status": "error", "database": "unavailable"}, 503


if __name__ == "__main__":
    initialize_database()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000"))
    )
