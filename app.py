"""
SISCC — Aplicación principal
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Debes iniciar sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    cfg = config[config_name]
    app.config.from_object(cfg)

    # Permite que ProductionConfig inyecte DATABASE_URL desde el entorno
    cfg.init_app(app)

    # Crear carpeta de uploads si no existe
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    # Registrar blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.vacantes import vacantes_bp
    from routes.candidatos import candidatos_bp
    from routes.induccion import induccion_bp
    from routes.admin import admin_bp
    from routes.api import api_bp
    from routes.analisis_ia import analisis_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(vacantes_bp, url_prefix='/vacantes')
    app.register_blueprint(candidatos_bp, url_prefix='/candidatos')
    app.register_blueprint(induccion_bp, url_prefix='/induccion')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(analisis_bp)

    # Filtro Jinja2: convierte JSON string en dict (usado en detalle candidato)
    import json as _json
    app.jinja_env.filters['fromjson'] = lambda s: _json.loads(s) if s else {}

    # Crear tablas y datos iniciales
    with app.app_context():
        db.create_all()
        _seed_inicial()

    return app


def _seed_inicial():
    """Crea datos iniciales si la BD está vacía."""
    from models import Rol, Usuario, ModuloInduccion, PreguntaQuiz

    # Roles
    if Rol.query.count() == 0:
        roles = [
            Rol(nombre='admin', descripcion='Administrador del sistema — acceso total'),
            Rol(nombre='rrhh', descripcion='Gestión de talento humano — acceso completo RRHH'),
            Rol(nombre='reclutador', descripcion='Publicar vacantes y ver HV'),
            Rol(nombre='psicologo', descripcion='Evaluaciones psicológicas'),
            Rol(nombre='nomina', descripcion='Contratos y nómina'),
            Rol(nombre='candidato', descripcion='Portal de postulación'),
        ]
        db.session.add_all(roles)
        db.session.commit()

    # Usuario admin por defecto
    if Usuario.query.count() == 0:
        rol_admin = Rol.query.filter_by(nombre='admin').first()
        admin = Usuario(
            nombre='Administrador SISCC',
            email='admin@siscc.co',
            rol_id=rol_admin.id,
            activo=True
        )
        admin.set_password('Admin2024!')
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuario admin creado: admin@siscc.co / Admin2024!")

    # Módulos de inducción
    if ModuloInduccion.query.count() == 0:
        modulos = [
            ModuloInduccion(
                numero=1,
                titulo='Amenazas Digitales: Phishing y Malware',
                descripcion='Identifica intentos de engaño, correos fraudulentos y archivos maliciosos en el entorno corporativo.',
                duracion_min=20,
                obligatorio=True,
                puntaje_minimo=70,
                contenido_html="""
                <h2>¿Qué es el Phishing?</h2>
                <p>El phishing es una técnica de ingeniería social en la que un atacante se hace pasar por una entidad de confianza para robar información sensible como contraseñas o datos bancarios.</p>
                <h3>Señales de alerta en un correo:</h3>
                <ul>
                  <li>Remitente con dominio sospechoso (ej: banco-xyz.ru)</li>
                  <li>Urgencia artificial ("tu cuenta será bloqueada en 2 horas")</li>
                  <li>Errores ortográficos o gramaticales</li>
                  <li>Links que no coinciden con el dominio real</li>
                  <li>Solicitud de datos personales por correo</li>
                </ul>
                <h2>¿Qué es el Malware?</h2>
                <p>Software malicioso diseñado para dañar, robar información o tomar control de sistemas. Tipos comunes: virus, ransomware, spyware, troyanos.</p>
                <h3>Cómo protegerte:</h3>
                <ul>
                  <li>Nunca abras archivos adjuntos de remitentes desconocidos</li>
                  <li>Mantén tu sistema operativo y antivirus actualizados</li>
                  <li>Reporta inmediatamente cualquier actividad sospechosa a TI</li>
                </ul>
                """
            ),
            ModuloInduccion(
                numero=2,
                titulo='Gestión de Contraseñas y Autenticación',
                descripcion='Buenas prácticas para crear, almacenar y rotar contraseñas. Activación de 2FA.',
                duracion_min=15,
                obligatorio=True,
                puntaje_minimo=70,
                contenido_html="""
                <h2>Contraseñas seguras</h2>
                <p>Una contraseña segura tiene mínimo 12 caracteres, combina mayúsculas, minúsculas, números y símbolos, y no contiene información personal.</p>
                <h3>Reglas de oro:</h3>
                <ul>
                  <li>Nunca reutilices contraseñas entre servicios</li>
                  <li>Usa un gestor de contraseñas (Bitwarden, 1Password)</li>
                  <li>Cambia contraseñas comprometidas inmediatamente</li>
                  <li>Activa autenticación de dos factores (2FA) siempre que sea posible</li>
                </ul>
                <h2>Autenticación de Dos Factores (2FA)</h2>
                <p>El 2FA añade una capa adicional de seguridad. Incluso si alguien obtiene tu contraseña, no podrá acceder sin el segundo factor (código en tu teléfono).</p>
                """
            ),
            ModuloInduccion(
                numero=3,
                titulo='Privacidad y Habeas Data en el trabajo',
                descripcion='Manejo de datos personales, Ley 1581 y responsabilidades del empleado.',
                duracion_min=10,
                obligatorio=True,
                puntaje_minimo=70,
                contenido_html="""
                <h2>Ley 1581 de 2012 — Habeas Data</h2>
                <p>En Colombia, la Ley 1581 protege el derecho de las personas a conocer, actualizar, rectificar y suprimir la información que sobre ellas se tenga en bases de datos.</p>
                <h3>Como empleado debes:</h3>
                <ul>
                  <li>Acceder solo a la información necesaria para tu rol</li>
                  <li>No compartir datos de clientes o colegas sin autorización</li>
                  <li>Reportar brechas de seguridad inmediatamente</li>
                  <li>Firmar y cumplir acuerdos de confidencialidad</li>
                </ul>
                <h2>Datos sensibles en el entorno laboral</h2>
                <p>Salarios, evaluaciones, datos médicos, información familiar — son datos que requieren protección especial y acceso restringido según el principio de mínimo privilegio.</p>
                """
            ),
        ]
        db.session.add_all(modulos)
        db.session.commit()

        # Preguntas quiz módulo 1
        m1 = ModuloInduccion.query.filter_by(numero=1).first()
        preguntas_m1 = [
            PreguntaQuiz(
                modulo_id=m1.id, orden=1,
                pregunta='Recibes un correo del "Banco Popular" indicando que tu cuenta fue bloqueada. El enlace apunta a http://banco-popular-seguro.ru/login. ¿Qué haces?',
                opcion_a='Ingresas al enlace rápidamente para desbloquear la cuenta',
                opcion_b='Reenvías el correo a tus compañeros para advertirles',
                opcion_c='Reportas el correo al equipo de seguridad TI y lo eliminas sin hacer clic',
                opcion_d='Llamas al banco por el número que viene en el correo',
                respuesta_correcta='c',
                explicacion='Los correos de phishing usan dominios similares pero distintos (.ru, .net, etc.) y crean urgencia. Siempre reporta al equipo TI y nunca hagas clic en enlaces sospechosos.'
            ),
            PreguntaQuiz(
                modulo_id=m1.id, orden=2,
                pregunta='Un archivo adjunto en un correo de un proveedor conocido tiene extensión .exe. ¿Qué haces?',
                opcion_a='Lo abres porque conoces al proveedor',
                opcion_b='Lo abres solo si el asunto parece legítimo',
                opcion_c='Lo reenvías a un colega para que lo revise',
                opcion_d='No lo abres, contactas al proveedor por otro medio para verificar y reportas a TI',
                respuesta_correcta='d',
                explicacion='Los archivos .exe son ejecutables que pueden contener malware. Verifica siempre por un canal separado antes de abrir cualquier adjunto inusual.'
            ),
            PreguntaQuiz(
                modulo_id=m1.id, orden=3,
                pregunta='¿Cuál de estas es la señal MÁS clara de un intento de phishing?',
                opcion_a='El correo tiene el logo de la empresa',
                opcion_b='El remitente usa un dominio distinto al oficial y crea urgencia',
                opcion_c='El correo está escrito en español perfecto',
                opcion_d='El correo llega en horario laboral',
                respuesta_correcta='b',
                explicacion='El indicador más confiable es el dominio del remitente. Verifica siempre que coincida exactamente con el dominio oficial de la empresa.'
            ),
        ]
        db.session.add_all(preguntas_m1)

        # Preguntas quiz módulo 2
        m2 = ModuloInduccion.query.filter_by(numero=2).first()
        preguntas_m2 = [
            PreguntaQuiz(
                modulo_id=m2.id, orden=1,
                pregunta='¿Cuál de estas contraseñas es la más segura?',
                opcion_a='password123',
                opcion_b='MiNombre1990',
                opcion_c='Tr0mb0n#Azul!2024',
                opcion_d='abc123456',
                respuesta_correcta='c',
                explicacion='Una contraseña segura combina mayúsculas, minúsculas, números y símbolos, y no contiene información personal.'
            ),
            PreguntaQuiz(
                modulo_id=m2.id, orden=2,
                pregunta='¿Para qué sirve el 2FA (Autenticación de Dos Factores)?',
                opcion_a='Para recordar contraseñas más fácilmente',
                opcion_b='Para acceder más rápido al sistema',
                opcion_c='Para añadir una segunda capa de seguridad aunque roben tu contraseña',
                opcion_d='Para cambiar la contraseña automáticamente',
                respuesta_correcta='c',
                explicacion='El 2FA garantiza que incluso si alguien obtiene tu contraseña, necesitará un segundo factor (generalmente tu teléfono) para acceder.'
            ),
        ]
        db.session.add_all(preguntas_m2)

        # Preguntas quiz módulo 3
        m3 = ModuloInduccion.query.filter_by(numero=3).first()
        preguntas_m3 = [
            PreguntaQuiz(
                modulo_id=m3.id, orden=1,
                pregunta='Según la Ley 1581 de Colombia, ¿qué derecho tienen las personas sobre sus datos personales?',
                opcion_a='Solo el derecho a eliminarlos',
                opcion_b='Conocer, actualizar, rectificar y solicitar supresión de sus datos',
                opcion_c='Solo el derecho a verlos, no a modificarlos',
                opcion_d='Ningún derecho si los datos son del empleador',
                respuesta_correcta='b',
                explicacion='La Ley 1581 reconoce los derechos de acceso, actualización, rectificación, supresión, queja y revocación del consentimiento sobre datos personales.'
            ),
            PreguntaQuiz(
                modulo_id=m3.id, orden=2,
                pregunta='Tu colega te pide el salario de otro empleado porque "es para un proyecto". ¿Qué haces?',
                opcion_a='Se lo das porque confías en él',
                opcion_b='Le envías el dato por WhatsApp para que quede privado',
                opcion_c='Te niegas — esa información es confidencial y solo accesible según roles autorizados',
                opcion_d='Le pides que lo busque en el sistema con sus propias credenciales',
                respuesta_correcta='c',
                explicacion='La información salarial es dato sensible. Solo personal autorizado (nómina, gerencia) puede acceder a ella.'
            ),
        ]
        db.session.add_all(preguntas_m3)
        db.session.commit()
        print("✅ Módulos de inducción y preguntas quiz creados")
