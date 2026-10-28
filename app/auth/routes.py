from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User
from app.services.complaint_service import audit

from .forms import LoginForm, RegisterForm

auth_bp = Blueprint("auth", __name__)


def dashboard_for(user):
    if user.role == "admin":
        return "admin.dashboard"
    if user.role == "maintenance":
        return "maintenance.dashboard"
    return "reporter.dashboard"


def _demo_user(role):
    email = f"demo-{role}@campusfix.local"
    user = User.query.filter_by(email=email).first()
    labels = {
        "reporter": ("Demo Student", "Student Affairs"),
        "admin": ("Demo Administrator", "Administration"),
        "maintenance": ("Maintenance Staff", "Maintenance"),
    }
    full_name, department = labels[role]
    if user:
        if role == "maintenance" and user.full_name.startswith("Demo"):
            user.full_name = full_name
            db.session.commit()
        return user
    user = User(full_name=full_name, email=email, role=role, department=department, is_active=True)
    user.set_password("Demo@12345")
    db.session.add(user)
    db.session.flush()
    audit(user, "demo_register", "User", user.id, f"Created demo {role} account")
    db.session.commit()
    return user


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_for(current_user)))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
        elif not user.is_active:
            flash("This account has been deactivated.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            audit(user, "login", "User", user.id, "User logged in")
            db.session.commit()
            return redirect(request.args.get("next") or url_for(dashboard_for(user)))
    return render_template("auth/login.html", form=form)


@auth_bp.route("/demo-login/<role>", methods=["POST"])
def demo_login(role):
    if role not in ("reporter", "admin", "maintenance"):
        flash("Demo role is not available.", "danger")
        return redirect(url_for("auth.login"))
    user = _demo_user(role)
    login_user(user)
    audit(user, "demo_login", "User", user.id, f"Demo login as {role}")
    db.session.commit()
    if role == "reporter":
        return redirect(url_for("reporter.submit_complaint"))
    return redirect(url_for(dashboard_for(user)))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_for(current_user)))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("Email is already registered.", "danger")
        else:
            user = User(full_name=form.full_name.data, email=email, role="reporter", department=form.department.data, phone=form.phone.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            audit(user, "register", "User", user.id, "Reporter account registered")
            db.session.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
