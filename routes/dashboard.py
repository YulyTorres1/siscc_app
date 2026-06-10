from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import Vacante, Candidato, LogAuditoria

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Redirigir candidatos a su portal de inducción
    if current_user.rol.nombre == 'candidato':
        return redirect(url_for('induccion.mi_induccion'))

    # Tarjetas principales
    total_vacantes = Vacante.query.filter_by(estado='activa').count()
    total_candidatos = Candidato.query.count()

    en_proceso = Candidato.query.filter(
        Candidato.estado.in_([
            'prefiltro',
            'evaluacion',
            'entrevista'
        ])
    ).count()

    induccion_completa = sum(
        1 for c in Candidato.query.all()
        if c.induccion_completa
    )

    # Pipeline
    estados = [
        'recibido',
        'prefiltro',
        'evaluacion',
        'entrevista',
        'seleccionado',
        'rechazado'
    ]

    pipeline = {
        estado: Candidato.query.filter_by(estado=estado).count()
        for estado in estados
    }

    # Fuentes de candidatos
    fuentes = {
        'portal': Candidato.query.filter_by(fuente='portal').count(),
        'spe': Candidato.query.filter_by(fuente='spe').count(),
        'sena': Candidato.query.filter_by(fuente='sena').count(),
        'referido': Candidato.query.filter_by(fuente='referido').count(),
    }

    # Actividad reciente
    logs_recientes = (
        LogAuditoria.query
        .order_by(LogAuditoria.fecha.desc())
        .limit(10)
        .all()
    )

    return render_template(
        'dashboard/index.html',
        total_vacantes=total_vacantes,
        total_candidatos=total_candidatos,
        en_proceso=en_proceso,
        induccion_completa=induccion_completa,
        pipeline=pipeline,
        fuentes=fuentes,
        logs_recientes=logs_recientes
    )
