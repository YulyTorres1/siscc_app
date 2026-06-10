"""
SISCC — Rutas de Autenticación
Login, Logout, Registro de candidatos, Cambio de contraseña
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models import Usuario, Rol, LogAuditoria

auth_bp = Blueprint('auth', __name__)


def registrar_log(accion, descripcion, recurso_tipo=None, recurso_id=None, resultado='ok'):
    log = LogAuditoria(
        usuario_id=current_user.id if not current_user.is_anonymous else None,
        accion=accion,
        descripcion=descripcion,
        ip=request.remote_addr,
        recurso_tipo=recurso_tipo,
        recurso_id=recurso_id,
        resultado=resultado
    )
    db.session.add(log)
    db.session.commit()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        usuario = Usuario.query.filter_by(email=email, activo=True).first()

        if usuario and usuario.check_password(password):
            login_user(usuario, remember=remember)
            usuario.ultimo_login = datetime.utcnow()
            db.session.commit()

            # Registrar login exitoso
            log = LogAuditoria(
                usuario_id=usuario.id,
                accion='LOGIN',
                descripcion=f'Inicio de sesión exitoso',
                ip=request.remote_addr,
                recurso_tipo='login',
                resultado='ok'
            )
            db.session.add(log)
            db.session.commit()

            # Redirigir según rol
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if usuario.rol.nombre == 'candidato':
                return redirect(url_for('induccion.mi_induccion'))
            return redirect(url_for('dashboard.index'))
        else:
            # Log intento fallido
            log = LogAuditoria(
                accion='LOGIN_FALLIDO',
                descripcion=f'Intento fallido para email: {email}',
                ip=request.remote_addr,
                recurso_tipo='login',
                resultado='error'
            )
            db.session.add(log)
            db.session.commit()
            flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    registrar_log('LOGOUT', 'Cierre de sesión')
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro público para candidatos."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirmar = request.form.get('confirmar', '')

        # Validaciones
        errores = []
        if not nombre or len(nombre) < 3:
            errores.append('El nombre debe tener al menos 3 caracteres.')
        if not email or '@' not in email:
            errores.append('Correo electrónico inválido.')
        if Usuario.query.filter_by(email=email).first():
            errores.append('Este correo ya está registrado.')
        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if password != confirmar:
            errores.append('Las contraseñas no coinciden.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('auth/registro.html', form_data=request.form)

        rol_candidato = Rol.query.filter_by(nombre='candidato').first()
        nuevo = Usuario(
            nombre=nombre,
            email=email,
            rol_id=rol_candidato.id,
            activo=True
        )
        nuevo.set_password(password)
        db.session.add(nuevo)
        db.session.commit()

        flash('¡Cuenta creada exitosamente! Inicia sesión para continuar.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/registro.html')


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        actual = request.form.get('password_actual', '')
        nueva = request.form.get('password_nueva', '')
        confirmar = request.form.get('confirmar', '')

        if not current_user.check_password(actual):
            flash('La contraseña actual es incorrecta.', 'danger')
        elif len(nueva) < 8:
            flash('La nueva contraseña debe tener al menos 8 caracteres.', 'danger')
        elif nueva != confirmar:
            flash('Las contraseñas no coinciden.', 'danger')
        else:
            current_user.set_password(nueva)
            db.session.commit()
            registrar_log('CAMBIO_PASSWORD', 'Contraseña actualizada')
            flash('Contraseña actualizada correctamente.', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('auth/cambiar_password.html')
