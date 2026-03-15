from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ...models import User
from .forms import LoginForm

auth_bp = Blueprint("auth", __name__, template_folder="templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        user = User.query.filter_by(username=username).first()
        if user is None or not user.is_active or not user.check_password(form.password.data):
            flash("Nieprawidłowy login lub hasło.", "danger")
        else:
            login_user(user)
            next_url = request.args.get("next", "").strip()
            if next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Wylogowano.", "success")
    return redirect(url_for("auth.login"))
