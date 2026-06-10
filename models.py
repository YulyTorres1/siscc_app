"""
SISCC — Modelos de base de datos
Todos los modelos del sistema: usuarios, roles, vacantes, candidatos, inducción, auditoría
"""
from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


# ── Tabla intermedia: roles de usuario ─────────────────────────────────────
class Rol(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    # admin, rrhh, psicologo, nomina, reclutador, candidato
    descripcion = db.Column(db.String(200))
    usuarios = db.relationship('Usuario', backref='rol', lazy=True)

    def __repr__(self):
        return f'<Rol {self.nombre}>'


# ── Usuario ─────────────────────────────────────────────────────────────────
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_login = db.Column(db.DateTime)
    avatar = db.Column(db.String(200), default='default.png')

    # Relaciones
    logs = db.relationship('LogAuditoria', backref='usuario', lazy=True)
    candidato = db.relationship('Candidato', backref='usuario', uselist=False)

    def set_password(self, password):
        from flask_bcrypt import generate_password_hash
        self.password_hash = generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        from flask_bcrypt import check_password_hash
        return check_password_hash(self.password_hash, password)

    def tiene_rol(self, *roles):
        return self.rol.nombre in roles

    def __repr__(self):
        return f'<Usuario {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ── Vacante ─────────────────────────────────────────────────────────────────
class Vacante(db.Model):
    __tablename__ = 'vacantes'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    departamento = db.Column(db.String(100))
    descripcion = db.Column(db.Text, nullable=False)
    requisitos = db.Column(db.Text)
    habilidades = db.Column(db.String(500))   # CSV: "Python,Django,REST"
    modalidad = db.Column(db.String(50))       # Remoto / Presencial / Híbrido
    tipo_contrato = db.Column(db.String(80))
    salario_min = db.Column(db.Integer)
    salario_max = db.Column(db.Integer)
    estado = db.Column(db.String(20), default='activa')  # activa, pausada, cerrada
    publicada_spe = db.Column(db.Boolean, default=False)
    publicada_sena = db.Column(db.Boolean, default=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime)
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    candidatos = db.relationship('Candidato', backref='vacante', lazy=True)

    @property
    def habilidades_lista(self):
        return [h.strip() for h in self.habilidades.split(',')] if self.habilidades else []

    @property
    def total_candidatos(self):
        return len(self.candidatos)

    def __repr__(self):
        return f'<Vacante {self.titulo}>'


# ── Candidato ───────────────────────────────────────────────────────────────
class Candidato(db.Model):
    __tablename__ = 'candidatos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    vacante_id = db.Column(db.Integer, db.ForeignKey('vacantes.id'))

    # Datos personales
    nombre = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(20))
    documento = db.Column(db.String(20))
    tipo_documento = db.Column(db.String(10), default='CC')
    perfil = db.Column(db.Text)

    # Proceso
    fuente = db.Column(db.String(50), default='portal')   # spe, sena, portal, referido
    estado = db.Column(db.String(30), default='recibido')
    # recibido → prefiltro → evaluacion → entrevista → seleccionado → induccion → activo → rechazado
    score = db.Column(db.Integer, default=0)
    notas_rrhh = db.Column(db.Text)

    # Documento HV
    hv_archivo = db.Column(db.String(300))
    hv_escaneada = db.Column(db.Boolean, default=False)
    hv_limpia = db.Column(db.Boolean, default=False)   # resultado escaneo malware

    # Consentimientos
    acepta_habeas_data = db.Column(db.Boolean, default=False)
    acepta_induccion = db.Column(db.Boolean, default=False)
    fecha_consentimiento = db.Column(db.DateTime)

    fecha_postulacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    evaluaciones = db.relationship('Evaluacion', backref='candidato', lazy=True)
    progreso_induccion = db.relationship('ProgresoModulo', backref='candidato', lazy=True)

    @property
    def induccion_completa(self):
        modulos_obligatorios = ModuloInduccion.query.filter_by(obligatorio=True).count()
        completados = ProgresoModulo.query.filter_by(
            candidato_id=self.id, aprobado=True
        ).count()
        return completados >= modulos_obligatorios

    def __repr__(self):
        return f'<Candidato {self.nombre}>'


# ── Evaluación psicológica ───────────────────────────────────────────────────
class Evaluacion(db.Model):
    __tablename__ = 'evaluaciones'
    id = db.Column(db.Integer, primary_key=True)
    candidato_id = db.Column(db.Integer, db.ForeignKey('candidatos.id'), nullable=False)
    evaluador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    tipo = db.Column(db.String(50))   # psicologica, tecnica, entrevista
    resultado = db.Column(db.Text)
    puntaje = db.Column(db.Integer)
    recomendacion = db.Column(db.String(20))  # apto, no_apto, en_espera
    archivo = db.Column(db.String(300))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Evaluacion {self.tipo} - {self.candidato_id}>'


# ── Módulos de inducción ─────────────────────────────────────────────────────
class ModuloInduccion(db.Model):
    __tablename__ = 'modulos_induccion'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    contenido_html = db.Column(db.Text)   # contenido del módulo
    duracion_min = db.Column(db.Integer, default=20)
    obligatorio = db.Column(db.Boolean, default=True)
    puntaje_minimo = db.Column(db.Integer, default=70)  # % mínimo para aprobar
    activo = db.Column(db.Boolean, default=True)

    preguntas = db.relationship('PreguntaQuiz', backref='modulo', lazy=True)
    progresos = db.relationship('ProgresoModulo', backref='modulo', lazy=True)

    def __repr__(self):
        return f'<Modulo {self.numero}: {self.titulo}>'


class PreguntaQuiz(db.Model):
    __tablename__ = 'preguntas_quiz'
    id = db.Column(db.Integer, primary_key=True)
    modulo_id = db.Column(db.Integer, db.ForeignKey('modulos_induccion.id'), nullable=False)
    pregunta = db.Column(db.Text, nullable=False)
    opcion_a = db.Column(db.String(500), nullable=False)
    opcion_b = db.Column(db.String(500), nullable=False)
    opcion_c = db.Column(db.String(500), nullable=False)
    opcion_d = db.Column(db.String(500), nullable=False)
    respuesta_correcta = db.Column(db.String(1), nullable=False)  # a, b, c, d
    explicacion = db.Column(db.Text)
    orden = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Pregunta {self.id}>'


class ProgresoModulo(db.Model):
    __tablename__ = 'progreso_modulos'
    id = db.Column(db.Integer, primary_key=True)
    candidato_id = db.Column(db.Integer, db.ForeignKey('candidatos.id'), nullable=False)
    modulo_id = db.Column(db.Integer, db.ForeignKey('modulos_induccion.id'), nullable=False)
    iniciado = db.Column(db.Boolean, default=False)
    completado = db.Column(db.Boolean, default=False)
    aprobado = db.Column(db.Boolean, default=False)
    puntaje = db.Column(db.Integer, default=0)
    intentos = db.Column(db.Integer, default=0)
    fecha_inicio = db.Column(db.DateTime)
    fecha_completado = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Progreso modulo {self.modulo_id} - candidato {self.candidato_id}>'


# ── Log de Auditoría ─────────────────────────────────────────────────────────
class LogAuditoria(db.Model):
    __tablename__ = 'log_auditoria'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    accion = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    ip = db.Column(db.String(45))
    recurso_tipo = db.Column(db.String(50))   # candidato, vacante, archivo, login
    recurso_id = db.Column(db.Integer)
    resultado = db.Column(db.String(20), default='ok')  # ok, denegado, error
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Log {self.accion} - {self.fecha}>'
