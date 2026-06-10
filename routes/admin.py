from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from models import LogAuditoria, Usuario, Rol

admin_bp = Blueprint('admin', __name__)


def solo_admin(f):
    """Decorador: solo admin y rrhh pueden entrar."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.tiene_rol('admin', 'rrhh'):
            flash('No tienes permisos para acceder a esta sección.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@solo_admin
def index():
    logs = LogAuditoria.query.order_by(LogAuditoria.fecha.desc()).limit(100).all()
    usuarios = Usuario.query.order_by(Usuario.fecha_creacion.desc()).all()
    roles = Rol.query.all()
    return render_template('admin/index.html', logs=logs, usuarios=usuarios, roles=roles)


@admin_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@solo_admin
def nuevo_usuario():
    roles = Rol.query.all()
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        rol_id = request.form.get('rol_id')

        errores = []
        if not nombre or len(nombre) < 3:
            errores.append('El nombre debe tener al menos 3 caracteres.')
        if not email or '@' not in email:
            errores.append('Correo inválido.')
        if Usuario.query.filter_by(email=email).first():
            errores.append('Este correo ya está registrado.')
        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if not rol_id:
            errores.append('Debes seleccionar un rol.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('admin/nuevo_usuario.html', roles=roles)

        usuario = Usuario(
            nombre=nombre,
            email=email,
            rol_id=int(rol_id),
            activo=True
        )
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        flash(f'Usuario "{nombre}" creado exitosamente.', 'success')
        return redirect(url_for('admin.index'))

    return render_template('admin/nuevo_usuario.html', roles=roles)


@admin_bp.route('/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@solo_admin
def toggle_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if usuario.id == current_user.id:
        flash('No puedes desactivarte a ti mismo.', 'danger')
    else:
        usuario.activo = not usuario.activo
        db.session.commit()
        estado = 'activado' if usuario.activo else 'desactivado'
        flash(f'Usuario {estado}.', 'info')
    return redirect(url_for('admin.index'))


@admin_bp.route('/usuarios/<int:id>/cambiar-password', methods=['POST'])
@login_required
@solo_admin
def reset_password(id):
    usuario = Usuario.query.get_or_404(id)
    nueva = request.form.get('nueva_password', '')
    if len(nueva) < 8:
        flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
    else:
        usuario.set_password(nueva)
        db.session.commit()
        flash(f'Contraseña de {usuario.nombre} actualizada.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/auditoria')
@login_required
@solo_admin
def auditoria():
    logs = LogAuditoria.query.order_by(LogAuditoria.fecha.desc()).limit(200).all()
    return render_template('admin/auditoria.html', logs=logs)
