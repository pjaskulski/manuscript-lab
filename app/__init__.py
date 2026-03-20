from pathlib import Path

import click
from flask import Flask, flash, redirect, request, url_for
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, login_manager, migrate
from .models.parameter import ParameterModel, ParameterPrompt
from .models.scan import Scan
from .models.user import User
from .services.concurrency import ConcurrentUpdateError
from .services.model_registry import (
    MANUAL_MODEL_NAME,
    MODEL_SCOPE_HTR,
    MODEL_SCOPE_TRANSLATION,
)
from .services.file_storage import ensure_scan_thumbnail, thumbnail_relative_path_for


def _rebuild_documents_table_for_composite_uniqueness(document_columns: set[str]) -> None:
    optional_columns: list[str] = []
    if "bibliographic_address" in document_columns:
        optional_columns.append("bibliographic_address VARCHAR(512)")
    if "reference_translation_pl" in document_columns:
        optional_columns.append("reference_translation_pl TEXT")

    new_table_columns = [
        "id INTEGER NOT NULL",
        "title VARCHAR(255) NOT NULL",
        "document_code VARCHAR(128)",
        *optional_columns,
        "notes TEXT",
        "original_text TEXT",
        "created_at DATETIME NOT NULL",
        "updated_at DATETIME NOT NULL",
        "is_done BOOLEAN NOT NULL DEFAULT 0",
        "PRIMARY KEY (id)",
        "CONSTRAINT uq_document_code_title UNIQUE (document_code, title)",
    ]

    copy_columns = [
        "id",
        "title",
        "document_code",
        *[column.split()[0] for column in optional_columns],
        "notes",
        "original_text",
        "created_at",
        "updated_at",
        "is_done",
    ]
    column_list = ", ".join(copy_columns)

    with db.engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("ALTER TABLE documents RENAME TO documents__old")
        connection.exec_driver_sql(f"CREATE TABLE documents ({', '.join(new_table_columns)})")
        connection.exec_driver_sql(
            f"INSERT INTO documents ({column_list}) SELECT {column_list} FROM documents__old"
        )
        connection.exec_driver_sql("DROP TABLE documents__old")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _documents_table_sql() -> str:
    with db.engine.begin() as connection:
        row = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'documents'")
        ).scalar()
    return (row or "").lower()


def _ensure_sqlite_compat_schema(app: Flask) -> None:
    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not database_uri.startswith("sqlite:///"):
        return

    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("scans"):
            return
        if not inspector.has_table("parameter_models"):
            ParameterModel.__table__.create(bind=db.engine)
            inspector = inspect(db.engine)
        scan_columns = {column["name"] for column in inspector.get_columns("scans")}
        if "is_training_sample" not in scan_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE scans ADD COLUMN is_training_sample BOOLEAN NOT NULL DEFAULT 0")
                )
        if "is_done" not in scan_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE scans ADD COLUMN is_done BOOLEAN NOT NULL DEFAULT 0"))
        if "main_ground_truth" not in {column["name"] for column in inspector.get_columns("scan_texts")}:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE scan_texts ADD COLUMN main_ground_truth BOOLEAN NOT NULL DEFAULT 0"))
        if not inspector.has_table("documents"):
            return
        document_columns = {column["name"] for column in inspector.get_columns("documents")}
        if "is_done" not in document_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE documents ADD COLUMN is_done BOOLEAN NOT NULL DEFAULT 0"))
            document_columns.add("is_done")
        if "bibliographic_address" not in document_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE documents ADD COLUMN bibliographic_address VARCHAR(512)"))
            document_columns.add("bibliographic_address")
        documents_table_sql = _documents_table_sql()
        has_old_unique = "unique (document_code)" in documents_table_sql
        has_composite_unique = "unique (document_code, title)" in documents_table_sql
        if has_old_unique or not has_composite_unique:
            _rebuild_documents_table_for_composite_uniqueness(document_columns)
            inspector = inspect(db.engine)
        if inspector.has_table("translation_comparisons"):
            comparison_columns = {column["name"] for column in inspector.get_columns("translation_comparisons")}
            if "chrf" not in comparison_columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE translation_comparisons ADD COLUMN chrf FLOAT"))
        if inspector.has_table("translation_variants"):
            translation_variant_columns = {column["name"] for column in inspector.get_columns("translation_variants")}
            if "source_prompt" not in translation_variant_columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE translation_variants ADD COLUMN source_prompt VARCHAR(128)"))


def _ensure_default_parameter_models(app: Flask) -> None:
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("parameter_models"):
            ParameterModel.__table__.create(bind=db.engine)
        if not inspector.has_table("parameter_prompts"):
            ParameterPrompt.__table__.create(bind=db.engine)
        for scope in (MODEL_SCOPE_HTR, MODEL_SCOPE_TRANSLATION):
            exists = ParameterModel.query.filter_by(scope=scope, name=MANUAL_MODEL_NAME).first()
            if exists is None:
                db.session.add(ParameterModel(scope=scope, name=MANUAL_MODEL_NAME))
        db.session.commit()


def _ensure_auth_schema(app: Flask) -> None:
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("users"):
            User.__table__.create(bind=db.engine)


@event.listens_for(Engine, "connect")
def _configure_sqlite_connection(dbapi_connection, connection_record) -> None:
    if dbapi_connection.__class__.__module__ != "sqlite3":
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


def _register_error_handlers(app: Flask) -> None:
    def _redirect_target() -> str:
        return request.referrer or url_for("main.index")

    @app.errorhandler(ConcurrentUpdateError)
    def handle_concurrent_update(error: ConcurrentUpdateError):
        flash(str(error), "warning")
        return redirect(_redirect_target())

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error: IntegrityError):
        db.session.rollback()
        flash(
            "Nie udało się zapisać zmian, ponieważ dane zostały równocześnie zmienione albo naruszają ograniczenia unikalności.",
            "warning",
        )
        return redirect(_redirect_target())

    @app.errorhandler(OperationalError)
    def handle_operational_error(error: OperationalError):
        db.session.rollback()
        message = str(getattr(error, "orig", error)).lower()
        if "database is locked" in message:
            flash(
                "Baza danych jest chwilowo zajęta przez inny zapis. Spróbuj ponownie za moment.",
                "warning",
            )
            return redirect(_redirect_target())
        flash("Wystąpił błąd operacji na bazie danych. Spróbuj ponownie.", "danger")
        return redirect(_redirect_target())


def _register_auth(app: Flask) -> None:
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Zaloguj się, aby korzystać z aplikacji."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @app.before_request
    def require_login():
        if request.endpoint is None:
            return None
        if request.endpoint == "static":
            return None
        if request.endpoint.startswith("auth."):
            return None
        if current_user.is_authenticated:
            return None
        return login_manager.unauthorized()


def _register_cli_commands(app: Flask) -> None:
    @app.cli.command("create-user")
    @click.option("--username", prompt=True)
    @click.password_option("--password", prompt=True, confirmation_prompt=True)
    def create_user_command(username: str, password: str) -> None:
        normalized_username = username.strip()
        if not normalized_username:
            raise click.ClickException("Nazwa użytkownika nie może być pusta.")

        existing = User.query.filter_by(username=normalized_username).first()
        if existing is not None:
            raise click.ClickException("Użytkownik o tej nazwie już istnieje.")

        user = User(username=normalized_username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Utworzono użytkownika: {normalized_username}")

    @app.cli.command("generate-scan-thumbnails")
    @click.option("--force", is_flag=True, help="Przegeneruj miniatury nawet wtedy, gdy plik juz istnieje.")
    def generate_scan_thumbnails_command(force: bool) -> None:
        upload_dir = app.config["UPLOAD_FOLDER"]
        scans = Scan.query.filter(Scan.image_path.isnot(None)).order_by(Scan.id.asc()).all()
        generated = 0
        skipped = 0
        failed = 0

        for scan in scans:
            image_path = (scan.image_path or "").strip()
            if not image_path:
                skipped += 1
                continue

            thumbnail_path = Path(upload_dir) / thumbnail_relative_path_for(image_path)
            if thumbnail_path.exists() and not force:
                skipped += 1
                continue

            result = ensure_scan_thumbnail(image_path, upload_dir)
            if result:
                generated += 1
            else:
                failed += 1
                click.echo(f"Nie udalo sie wygenerowac miniatury dla skanu #{scan.id}: {image_path}", err=True)

        click.echo(
            f"Miniatury: wygenerowano {generated}, pominieto {skipped}, bledy {failed}."
        )


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["THUMBNAIL_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    _register_auth(app)

    from .models import document, htr, parameter, scan, translation, user  # noqa: F401

    _ensure_sqlite_compat_schema(app)
    _ensure_auth_schema(app)
    _ensure_default_parameter_models(app)

    from .blueprints.auth.routes import auth_bp
    from .blueprints.main.routes import main_bp
    from .blueprints.scans.routes import scans_bp
    from .blueprints.htr.routes import htr_bp
    from .blueprints.documents.routes import documents_bp
    from .blueprints.translations.routes import translations_bp
    from .blueprints.parameters.routes import parameters_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(scans_bp, url_prefix="/scans")
    app.register_blueprint(htr_bp, url_prefix="/htr")
    app.register_blueprint(documents_bp, url_prefix="/documents")
    app.register_blueprint(translations_bp, url_prefix="/translations")
    app.register_blueprint(parameters_bp, url_prefix="/parameters")
    _register_error_handlers(app)
    _register_cli_commands(app)

    return app
