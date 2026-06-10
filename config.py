"""
SISCC — Sistema Integral de Selección y Concientización
Configuración de la aplicación
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    """Render provee postgres://, SQLAlchemy requiere postgresql://"""
    url = os.environ.get('DATABASE_URL') or 'sqlite:///siscc.db'
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    # ── Seguridad ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-cambiar-en-produccion'
    WTF_CSRF_ENABLED = True

    # ── Base de datos ──────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Archivos ───────────────────────────────────────────────
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10 MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg'}

    # ── Email ──────────────────────────────────────────────────
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')


class DevelopmentConfig(Config):
    FLASK_DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'instance', 'siscc_dev.db'
    )


class ProductionConfig(Config):
    FLASK_DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
