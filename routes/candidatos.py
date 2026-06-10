from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from app import db
from models import Candidato, Vacante, Rol

candidatos_bp = Blueprint('candidatos', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
ESTADOS = ['recibido', 'prefiltro', 'evaluacion', 'entrevista', 'seleccionado', 'induccion', 'activo', 'rechazado']

# Roles que pueden VER candidatos
VER = ('admin', 'rrhh', 'reclutador', 'psicologo', 'nomina')
# Roles que pueden CAMBIAR ESTADO de candidatos
GESTIONAR = ('admin', 'rrhh', 'reclutador')
# Roles que pueden ver evaluaciones psicológicas
VER_PSICO = ('admin', 'rrhh', 'psicologo')


def requiere_rol(*roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.tiene_rol(*roles):
                flash('No tienes permisos para realizar esta acción.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@candidatos_bp.route('/')
@login_required
@requiere_rol(*VER)
def index():
    busqueda = request.args.get('q', '').strip()
    estado_filtro = request.args.get('estado', '')
    fuente_filtro = request.args.get('fuente', '')
    vacante_filtro = request.args.get('vacante', '')

    query = Candidato.query
    if busqueda:
        query = query.filter(
            (Candidato.nombre.ilike(f'%{busqueda}%')) |
            (Candidato.email.ilike(f'%{busqueda}%'))
        )
    if estado_filtro:
        query = query.filter_by(estado=estado_filtro)
    if fuente_filtro:
        query = query.filter_by(fuente=fuente_filtro)
    if vacante_filtro:
        try:
            query = query.filter_by(vacante_id=int(vacante_filtro))
        except ValueError:
            pass

    candidatos = query.order_by(Candidato.fecha_postulacion.desc()).all()
    return render_template(
        'candidatos/index.html',
        candidatos=candidatos,
        busqueda=busqueda,
        estado_filtro=estado_filtro,
        fuente_filtro=fuente_filtro,
        vacante_filtro=vacante_filtro,
        estados=ESTADOS
    )


@candidatos_bp.route('/detalle/<int:id>')
@login_required
@requiere_rol(*VER)
def detalle(id):
    candidato = Candidato.query.get_or_404(id)
    # Psicólogo NO ve datos salariales — se maneja en el template con current_user
    return render_template('candidatos/detalle.html', candidato=candidato, vacante=candidato.vacante)


@candidatos_bp.route('/detalle/<int:id>/estado', methods=['POST'])
@login_required
@requiere_rol(*GESTIONAR)
def cambiar_estado(id):
    candidato = Candidato.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    if nuevo_estado in ESTADOS:
        candidato.estado = nuevo_estado
        db.session.commit()
        flash(f'Estado actualizado a "{nuevo_estado}".', 'success')
    return redirect(url_for('candidatos.detalle', id=id))


@candidatos_bp.route('/postular', methods=['GET', 'POST'])
def postular():
    """Portal público — sin login."""
    vacantes = Vacante.query.filter_by(estado='activa').all()

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        documento = request.form.get('documento', '').strip()
        vacante_id = request.form.get('vacante_id')
        perfil = request.form.get('perfil', '').strip()
        acepta_habeas = request.form.get('habeas_data') == 'on'
        acepta_induccion = request.form.get('acepta_induccion') == 'on'

        errores = []
        if not nombre or len(nombre) < 3:
            errores.append('El nombre debe tener al menos 3 caracteres.')
        if not email or '@' not in email:
            errores.append('Correo electrónico inválido.')
        if not acepta_habeas:
            errores.append('Debes aceptar el tratamiento de datos personales.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('candidatos/postular.html', vacantes=vacantes)

        from models import Usuario
        usuario = Usuario.query.filter_by(email=email).first()
        if not usuario:
            rol_candidato = Rol.query.filter_by(nombre='candidato').first()
            usuario = Usuario(
                nombre=nombre,
                email=email,
                rol_id=rol_candidato.id,
                activo=True
            )
            import secrets
            usuario.set_password(secrets.token_urlsafe(12))
            db.session.add(usuario)
            db.session.flush()

        hv_archivo = None
        if 'hv_archivo' in request.files:
            f = request.files['hv_archivo']
            if f and f.filename and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                f.save(filepath)
                hv_archivo = filename

        candidato = Candidato(
            usuario_id=usuario.id,
            vacante_id=int(vacante_id) if vacante_id else None,
            nombre=nombre,
            email=email,
            telefono=telefono,
            documento=documento,
            perfil=perfil,
            hv_archivo=hv_archivo,
            acepta_habeas_data=acepta_habeas,
            acepta_induccion=acepta_induccion,
            fecha_consentimiento=datetime.utcnow() if acepta_habeas else None,
            fuente='portal'
        )
        db.session.add(candidato)
        db.session.commit()

        flash('¡Postulación recibida! Te contactaremos pronto.', 'success')
        return redirect(url_for('candidatos.postular'))

    return render_template('candidatos/postular.html', vacantes=vacantes)


@candidatos_bp.route('/detalle/<int:id>/notas', methods=['POST'])
@login_required
@requiere_rol(*GESTIONAR)
def guardar_notas(id):
    candidato = Candidato.query.get_or_404(id)
    candidato.notas_rrhh = request.form.get('notas_rrhh', '').strip()
    score_val = request.form.get('score', '0')
    try:
        candidato.score = max(0, min(100, int(score_val)))
    except ValueError:
        candidato.score = 0
    db.session.commit()
    flash('Notas guardadas.', 'success')
    return redirect(url_for('candidatos.detalle', id=id))


@candidatos_bp.route('/detalle/<int:id>/evaluacion', methods=['POST'])
@login_required
@requiere_rol(*VER_PSICO)
def guardar_evaluacion(id):
    candidato = Candidato.query.get_or_404(id)
    from models import Evaluacion
    tipo = request.form.get('tipo', 'psicologica')
    recomendacion = request.form.get('recomendacion', '')
    resultado = request.form.get('resultado', '').strip()
    puntaje_val = request.form.get('puntaje', '')
    try:
        puntaje = max(0, min(100, int(puntaje_val))) if puntaje_val else None
    except ValueError:
        puntaje = None

    nueva_eval = Evaluacion(
        candidato_id=candidato.id,
        evaluador_id=current_user.id,
        tipo=tipo,
        recomendacion=recomendacion if recomendacion else None,
        resultado=resultado if resultado else None,
        puntaje=puntaje
    )
    db.session.add(nueva_eval)
    db.session.commit()
    flash('Evaluación guardada.', 'success')
    return redirect(url_for('candidatos.detalle', id=id))
