from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import Vacante

vacantes_bp = Blueprint('vacantes', __name__)

# Roles que pueden VER vacantes
VER = ('admin', 'rrhh', 'reclutador', 'psicologo', 'nomina')
# Roles que pueden CREAR / EDITAR / ELIMINAR vacantes
GESTIONAR = ('admin', 'rrhh', 'reclutador')


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


@vacantes_bp.route('/')
@login_required
@requiere_rol(*VER)
def index():
    vacantes = Vacante.query.order_by(Vacante.fecha_creacion.desc()).all()
    return render_template('vacantes/index.html', vacantes=vacantes)


@vacantes_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@requiere_rol(*GESTIONAR)
def nueva():
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        if not titulo:
            flash('El título es obligatorio.', 'danger')
            return render_template('form.html', vacante=None, accion='nueva')

        vacante = Vacante(
            titulo=titulo,
            departamento=request.form.get('departamento', ''),
            descripcion=request.form.get('descripcion', ''),
            requisitos=request.form.get('requisitos', ''),
            habilidades=request.form.get('habilidades', ''),
            modalidad=request.form.get('modalidad', ''),
            tipo_contrato=request.form.get('tipo_contrato', ''),
            salario_min=int(request.form.get('salario_min') or 0),
            salario_max=int(request.form.get('salario_max') or 0),
            estado='activa',
            creador_id=current_user.id,
            publicada_spe=('publicar_spe' in request.form),
            publicada_sena=('publicar_sena' in request.form)
        )
        db.session.add(vacante)
        db.session.commit()
        flash('Vacante creada exitosamente.', 'success')
        return redirect(url_for('vacantes.index'))

    return render_template('form.html', vacante=None, accion='nueva')


@vacantes_bp.route('/detalle/<int:id>')
@login_required
@requiere_rol(*VER)
def detalle(id):
    vacante = Vacante.query.get_or_404(id)
    return render_template('vacantes/detalle.html', vacante=vacante)


@vacantes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@requiere_rol(*GESTIONAR)
def editar(id):
    vacante = Vacante.query.get_or_404(id)
    if request.method == 'POST':
        vacante.titulo = request.form.get('titulo', vacante.titulo).strip()
        vacante.departamento = request.form.get('departamento', vacante.departamento)
        vacante.descripcion = request.form.get('descripcion', vacante.descripcion)
        vacante.requisitos = request.form.get('requisitos', vacante.requisitos)
        vacante.habilidades = request.form.get('habilidades', vacante.habilidades)
        vacante.modalidad = request.form.get('modalidad', vacante.modalidad)
        vacante.tipo_contrato = request.form.get('tipo_contrato', vacante.tipo_contrato)
        vacante.salario_min = int(request.form.get('salario_min') or vacante.salario_min or 0)
        vacante.salario_max = int(request.form.get('salario_max') or vacante.salario_max or 0)
        vacante.estado = request.form.get('estado', vacante.estado)
        vacante.publicada_spe = ('publicar_spe' in request.form)
        vacante.publicada_sena = ('publicar_sena' in request.form)
        db.session.commit()
        flash('Vacante actualizada.', 'success')
        return redirect(url_for('vacantes.detalle', id=vacante.id))

    return render_template('form.html', vacante=vacante, accion='editar')


@vacantes_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@requiere_rol('admin', 'rrhh')
def eliminar(id):
    vacante = Vacante.query.get_or_404(id)
    db.session.delete(vacante)
    db.session.commit()
    flash('Vacante eliminada.', 'info')
    return redirect(url_for('vacantes.index'))
