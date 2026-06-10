"""
SISCC — Sistema Integral de Selección y Concientización
Configuración de la aplicación
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _db_url():
    """
    Lee DATABASE_URL en tiempo de ejecución (no de importación).
    Render inyecta esta variable después de que el módulo se importa,
    por eso debe leerse dentro de una función, no a nivel de clase.
    Convierte postgres:// → postgresql:// que requiere SQLAlchemy.
    """
    url = os.environ.get('DATABASE_URL', '')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url or None


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-cambiar-en-produccion'
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg'}
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    @classmethod
    def init_app(cls, app):
        pass


class DevelopmentConfig(Config):
    FLASK_DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'instance', 'siscc_dev.db'
    )


class ProductionConfig(Config):
    FLASK_DEBUG = False

    @classmethod
    def init_app(cls, app):
        # En producción la URL viene de la variable de entorno
        db_url = _db_url()
        if not db_url:
            raise RuntimeError(
                'DATABASE_URL no está definida. '
                'Configúrala en Render → Environment.'
            )
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
