from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import ModuloInduccion, ProgresoModulo, Candidato, PreguntaQuiz

induccion_bp = Blueprint('induccion', __name__)


def requiere_rol(*roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.tiene_rol(*roles):
                flash('No tienes permisos para acceder a esta sección.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator


@induccion_bp.route('/mi-induccion')
@login_required
@requiere_rol('candidato')
def mi_induccion():
    candidato = Candidato.query.filter_by(usuario_id=current_user.id).first()
    modulos = ModuloInduccion.query.filter_by(activo=True).order_by(ModuloInduccion.numero).all()

    if not candidato:
        flash('Tu cuenta no tiene un perfil de candidato asociado. Completa tu postulación primero.', 'warning')

    progresos = {}
    if candidato:
        for p in ProgresoModulo.query.filter_by(candidato_id=candidato.id).all():
            progresos[p.modulo_id] = p

    return render_template(
        'induccion/mi_induccion.html',
        candidato=candidato,
        modulos=modulos,
        progresos=progresos
    )


@induccion_bp.route('/modulo/<int:modulo_id>')
@login_required
@requiere_rol('candidato')
def ver_modulo(modulo_id):
    modulo = ModuloInduccion.query.get_or_404(modulo_id)
    candidato = Candidato.query.filter_by(usuario_id=current_user.id).first()

    progreso = None
    if candidato:
        progreso = ProgresoModulo.query.filter_by(
            candidato_id=candidato.id, modulo_id=modulo_id
        ).first()
        if not progreso:
            progreso = ProgresoModulo(
                candidato_id=candidato.id,
                modulo_id=modulo_id,
                iniciado=True,
                fecha_inicio=datetime.utcnow()
            )
            db.session.add(progreso)
            db.session.commit()
        elif not progreso.iniciado:
            progreso.iniciado = True
            progreso.fecha_inicio = datetime.utcnow()
            db.session.commit()

    preguntas = PreguntaQuiz.query.filter_by(modulo_id=modulo_id).order_by(PreguntaQuiz.orden).all()
    return render_template('induccion/modulo.html', modulo=modulo, progreso=progreso, preguntas=preguntas)


@induccion_bp.route('/modulo/<int:modulo_id>/quiz', methods=['POST'])
@login_required
@requiere_rol('candidato')
def submit_quiz(modulo_id):
    modulo = ModuloInduccion.query.get_or_404(modulo_id)
    candidato = Candidato.query.filter_by(usuario_id=current_user.id).first()

    if not candidato:
        flash('No tienes un perfil de candidato asociado.', 'danger')
        return redirect(url_for('induccion.mi_induccion'))

    preguntas = PreguntaQuiz.query.filter_by(modulo_id=modulo_id).all()
    correctas = sum(
        1 for p in preguntas
        if request.form.get(f'pregunta_{p.id}', '').lower() == p.respuesta_correcta.lower()
    )
    puntaje = int((correctas / len(preguntas)) * 100) if preguntas else 100
    aprobado = puntaje >= modulo.puntaje_minimo

    progreso = ProgresoModulo.query.filter_by(
        candidato_id=candidato.id, modulo_id=modulo_id
    ).first()
    if not progreso:
        progreso = ProgresoModulo(candidato_id=candidato.id, modulo_id=modulo_id)
        db.session.add(progreso)

    progreso.completado = True
    progreso.aprobado = aprobado
    progreso.puntaje = puntaje
    progreso.intentos = (progreso.intentos or 0) + 1
    progreso.fecha_completado = datetime.utcnow()
    db.session.commit()

    if aprobado:
        flash(f'¡Módulo aprobado con {puntaje}%! 🎉', 'success')
    else:
        flash(f'Puntaje: {puntaje}%. Necesitas {modulo.puntaje_minimo}% para aprobar. Puedes intentarlo de nuevo.', 'warning')

    return redirect(url_for('induccion.mi_induccion'))


@induccion_bp.route('/panel')
@login_required
@requiere_rol('admin', 'rrhh', 'reclutador')
def panel_admin():
    modulos = ModuloInduccion.query.order_by(ModuloInduccion.numero).all()
    # Progreso de todos los candidatos en inducción
    from models import Usuario
    candidatos_induccion = Candidato.query.filter(
        Candidato.estado.in_(['induccion', 'seleccionado'])
    ).all()
    return render_template('induccion/panel.html', modulos=modulos, candidatos=candidatos_induccion)
