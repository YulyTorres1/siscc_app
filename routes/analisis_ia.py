"""
SISCC — Análisis IA de candidatos
Compara la HV + perfil del candidato contra los requisitos de la vacante
usando la API de Groq (gratuita, sin tarjeta de crédito).
"""
import os
import json
import traceback
from groq import Groq
from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from models import Candidato, Evaluacion


analisis_bp = Blueprint('analisis', __name__)


# ── Roles permitidos ─────────────────────────────────────────────────────────
GESTIONAR = ('admin', 'rrhh', 'reclutador')

def requiere_rol(*roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.tiene_rol(*roles):
                return jsonify({'error': 'Sin permisos'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Extractor de texto de la HV ───────────────────────────────────────────────
def extraer_texto_hv(filepath):
    """Lee PDF o DOCX y devuelve el texto plano."""
    ext = filepath.rsplit('.', 1)[-1].lower()
    texto = ""

    if ext == 'pdf':
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        texto += t + "\n"
        except Exception as e:
            texto = f"[No se pudo leer el PDF: {e}]"

    elif ext in ('docx', 'doc'):
        try:
            from docx import Document
            doc = Document(filepath)
            texto = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            texto = f"[No se pudo leer el DOCX: {e}]"

    return texto.strip()[:6000]


# ── Llamada a Groq API (gratuita) ─────────────────────────────────────────────
def analizar_con_claude(candidato, vacante, texto_hv):
    """
    Llama a Groq (llama-3.3-70b) y devuelve un dict con:
    {
      "score": 0-100,
      "veredicto": "CUMPLE" | "CUMPLE PARCIALMENTE" | "NO CUMPLE",
      "fortalezas": ["..."],
      "brechas": ["..."],
      "resumen": "texto corto"
    }
    """
    api_key = os.environ.get('GROQ_API_KEY') or current_app.config.get('GROQ_API_KEY')
    
    print("=" * 50)
    print("GROQ_API_KEY encontrada:", bool(api_key))
    if api_key:
        print("Inicio:", api_key[:8])
        print("Longitud:", len(api_key))
    print("=" * 50)

    if not api_key:
        raise ValueError("GROQ_API_KEY no configurada en el .env")

    # Construir el prompt
    perfil_candidato = []
    if candidato.perfil:
        perfil_candidato.append(f"Presentación del candidato:\n{candidato.perfil}")
    if texto_hv:
        perfil_candidato.append(f"Contenido de la hoja de vida:\n{texto_hv}")
    if not perfil_candidato:
        perfil_candidato.append("(El candidato no adjuntó HV ni escribió presentación)")

    requisitos_vacante = []
    if vacante.descripcion:
        requisitos_vacante.append(f"Descripción del cargo:\n{vacante.descripcion}")
    if vacante.requisitos:
        requisitos_vacante.append(f"Requisitos:\n{vacante.requisitos}")
    if vacante.habilidades:
        requisitos_vacante.append(f"Habilidades requeridas: {vacante.habilidades}")

    prompt = f"""Eres un experto en selección de personal colombiano. Analiza si el candidato cumple con el perfil de la vacante.

=== VACANTE: {vacante.titulo} ===
{chr(10).join(requisitos_vacante)}

=== CANDIDATO: {candidato.nombre} ===
{chr(10).join(perfil_candidato)}

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin bloques de código, con esta estructura exacta:
{{
  "score": <número entero 0-100>,
  "veredicto": "<CUMPLE | CUMPLE PARCIALMENTE | NO CUMPLE>",
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>", "<fortaleza 3>"],
  "brechas": ["<brecha 1>", "<brecha 2>"],
  "resumen": "<2-3 oraciones explicando el veredicto>"
}}

Criterios para el score:
- 80-100: Cumple todos o casi todos los requisitos
- 50-79: Cumple parcialmente, tiene potencial pero le faltan elementos clave
- 0-49: No cumple los requisitos mínimos

Si no hay suficiente información en la HV, indica en brechas que falta información y da un score conservador."""

    try:
        client = Groq(api_key=api_key)

        chat = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto en selección de personal. Respondes SOLO con JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=1000
            response_format={"type": "json_object"}
        )

        raw = chat.choices[0].message.content.strip()

    except Exception as e:
        raise Exception(f"Error Groq API: {str(e)}")


    raw = raw.replace('```json', '').replace('```', '').strip()
    resultado = json.loads(raw)

    resultado.setdefault('score', 0)
    resultado.setdefault('veredicto', 'NO CUMPLE')
    resultado.setdefault('fortalezas', [])
    resultado.setdefault('brechas', [])
    resultado.setdefault('resumen', '')

    return resultado


# ── Ruta principal: ejecutar análisis ────────────────────────────────────────
@analisis_bp.route('/candidatos/detalle/<int:id>/analizar', methods=['POST'])
@login_required
@requiere_rol(*GESTIONAR)
def analizar(id):
    candidato = Candidato.query.get_or_404(id)
    vacante = candidato.vacante

    if not vacante:
        return jsonify({'error': 'El candidato no tiene vacante asignada'}), 400

    texto_hv = ""
    if candidato.hv_archivo:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
        filepath = os.path.join(upload_folder, candidato.hv_archivo)
        if os.path.exists(filepath):
            texto_hv = extraer_texto_hv(filepath)

    try:
        resultado = analizar_con_claude(candidato, vacante, texto_hv)
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error al analizar: {str(e)}'}), 500

    Evaluacion.query.filter_by(
        candidato_id=candidato.id,
        tipo='ia_screening'
    ).delete()

    eval_ia = Evaluacion(
        candidato_id=candidato.id,
        evaluador_id=current_user.id,
        tipo='ia_screening',
        puntaje=resultado['score'],
        recomendacion='apto' if resultado['score'] >= 70
                      else ('en_espera' if resultado['score'] >= 50 else 'no_apto'),
        resultado=json.dumps(resultado, ensure_ascii=False)
    )
    db.session.add(eval_ia)

    candidato.score = resultado['score']
    db.session.commit()

    return jsonify(resultado)
