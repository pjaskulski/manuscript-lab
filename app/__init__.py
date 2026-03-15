from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db, migrate
from .models.parameter import ParameterModel
from .services.model_registry import (
    MANUAL_MODEL_NAME,
    MODEL_SCOPE_HTR,
    MODEL_SCOPE_TRANSLATION,
)


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
        document_columns = {column["name"] for column in inspector.get_columns("documents")}
        if "is_done" not in document_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE documents ADD COLUMN is_done BOOLEAN NOT NULL DEFAULT 0"))
        if inspector.has_table("translation_comparisons"):
            comparison_columns = {column["name"] for column in inspector.get_columns("translation_comparisons")}
            if "chrf" not in comparison_columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE translation_comparisons ADD COLUMN chrf FLOAT"))


def _ensure_default_parameter_models(app: Flask) -> None:
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("parameter_models"):
            ParameterModel.__table__.create(bind=db.engine)
        for scope in (MODEL_SCOPE_HTR, MODEL_SCOPE_TRANSLATION):
            exists = ParameterModel.query.filter_by(scope=scope, name=MANUAL_MODEL_NAME).first()
            if exists is None:
                db.session.add(ParameterModel(scope=scope, name=MANUAL_MODEL_NAME))
        db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    from .models import document, htr, parameter, scan, translation  # noqa: F401

    _ensure_sqlite_compat_schema(app)
    _ensure_default_parameter_models(app)

    from .blueprints.main.routes import main_bp
    from .blueprints.scans.routes import scans_bp
    from .blueprints.htr.routes import htr_bp
    from .blueprints.documents.routes import documents_bp
    from .blueprints.translations.routes import translations_bp
    from .blueprints.parameters.routes import parameters_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(scans_bp, url_prefix="/scans")
    app.register_blueprint(htr_bp, url_prefix="/htr")
    app.register_blueprint(documents_bp, url_prefix="/documents")
    app.register_blueprint(translations_bp, url_prefix="/translations")
    app.register_blueprint(parameters_bp, url_prefix="/parameters")

    return app
