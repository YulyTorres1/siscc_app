"""
SISCC — Análisis IA de candidatos
Compara la HV + perfil del candidato contra los requisitos de la vacante
usando la API de Groq.
"""

import os
import json
import traceback

from groq import Groq
from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user

from app import db
from models import Candidato, Evaluacion


analisis_bp = Blueprint("analisis", __name__)


# ---------------------------------------------------
# ROLES
# ---------------------------------------------------

GESTIONAR = ("admin", "rrhh", "reclutador")


def requiere_rol(*roles):
    def decorator(f):
        from functools import wraps

        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.tiene_rol(*roles):
                return jsonify({"error": "Sin permisos"}), 403
            return f(*args, **kwargs)

        return decorated

    return decorator


# ---------------------------------------------------
# EXTRAER TEXTO HV
# ---------------------------------------------------

def extraer_texto_hv(filepath):

    ext = filepath.rsplit(".", 1)[-1].lower()
    texto = ""

    if ext == "pdf":
        try:
            import pdfplumber

            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        texto += t + "\n"

        except Exception as e:
            texto = f"[No se pudo leer PDF: {e}]"

    elif ext in ("doc", "docx"):

        try:
            from docx import Document

            doc = Document(filepath)

            texto = "\n".join(
                p.text
                for p in doc.paragraphs
                if p.text.strip()
            )

        except Exception as e:
            texto = f"[No se pudo leer DOCX: {e}]"

    return texto.strip()[:6000]


# ---------------------------------------------------
# IA
# ---------------------------------------------------

def analizar_con_groq(candidato, vacante, texto_hv):

    api_key = (
        os.environ.get("GROQ_API_KEY")
        or current_app.config.get("GROQ_API_KEY")
    )

    if not api_key:
        raise ValueError("GROQ_API_KEY no configurada.")

    perfil = []

    if candidato.perfil:
        perfil.append(
            f"Presentación:\n{candidato.perfil}"
        )

    if texto_hv:
        perfil.append(
            f"Hoja de vida:\n{texto_hv}"
        )

    if not perfil:
        perfil.append(
            "El candidato no adjuntó información."
        )

    requisitos = []

    if vacante.descripcion:
        requisitos.append(
            f"Descripción:\n{vacante.descripcion}"
        )

    if vacante.requisitos:
        requisitos.append(
            f"Requisitos:\n{vacante.requisitos}"
        )

    if vacante.habilidades:
        requisitos.append(
            f"Habilidades:\n{vacante.habilidades}"
        )

    prompt = f"""
Eres un experto en selección de personal colombiano.

VACANTE:
{vacante.titulo}

{chr(10).join(requisitos)}

CANDIDATO:
{candidato.nombre}

{chr(10).join(perfil)}

Responde EXCLUSIVAMENTE con JSON:

{{
"score":0,
"veredicto":"",
"fortalezas":[],
"brechas":[],
"resumen":""
}}

Reglas:

80-100 = CUMPLE

50-79 = CUMPLE PARCIALMENTE

0-49 = NO CUMPLE

Si falta información usa score conservador.
"""

    try:

        client = Groq(api_key=api_key)

        respuesta = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "Responde únicamente JSON válido."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],

            temperature=0.2,
            max_completion_tokens=1000,
        )

    except Exception as e:
        raise Exception(f"Error Groq: {e}")

    raw = respuesta.choices[0].message.content.strip()

    raw = raw.replace("```json", "")
    raw = raw.replace("```", "")
    raw = raw.strip()

    inicio = raw.find("{")
    fin = raw.rfind("}")

    if inicio == -1 or fin == -1:
        raise Exception(
            f"Groq no devolvió JSON válido:\n{raw}"
        )

    raw = raw[inicio:fin + 1]

    try:
        resultado = json.loads(raw)

    except Exception:
        raise Exception(
            f"JSON inválido:\n{raw}"
        )

    resultado.setdefault("score", 0)
    resultado.setdefault(
        "veredicto",
        "NO CUMPLE"
    )
    resultado.setdefault(
        "fortalezas",
        []
    )
    resultado.setdefault(
        "brechas",
        []
    )
    resultado.setdefault(
        "resumen",
        ""
    )

    return resultado


# ---------------------------------------------------
# RUTA
# ---------------------------------------------------

@analisis_bp.route(
    "/candidatos/detalle/<int:id>/analizar",
    methods=["POST"],
)
@login_required
@requiere_rol(*GESTIONAR)
def analizar(id):

    candidato = Candidato.query.get_or_404(id)

    vacante = candidato.vacante

    if not vacante:
        return jsonify({
            "error":
            "El candidato no tiene vacante."
        }), 400

    texto_hv = ""

    if candidato.hv_archivo:

        upload_folder = current_app.config.get(
            "UPLOAD_FOLDER",
            "static/uploads"
        )

        filepath = os.path.join(
            upload_folder,
            candidato.hv_archivo
        )

        if os.path.exists(filepath):
            texto_hv = extraer_texto_hv(filepath)

    try:

        resultado = analizar_con_groq(
            candidato,
            vacante,
            texto_hv
        )

    except ValueError as e:

        return jsonify({
            "error": str(e)
        }), 500

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error":
            f"Error al analizar: {e}"
        }), 500

    Evaluacion.query.filter_by(
        candidato_id=candidato.id,
        tipo="ia_screening"
    ).delete()

    evaluacion = Evaluacion(

        candidato_id=candidato.id,

        evaluador_id=current_user.id,

        tipo="ia_screening",

        puntaje=resultado["score"],

        recomendacion=(
            "apto"
            if resultado["score"] >= 70
            else (
                "en_espera"
                if resultado["score"] >= 50
                else "no_apto"
            )
        ),

        resultado=json.dumps(
            resultado,
            ensure_ascii=False
        )
    )

    db.session.add(evaluacion)

    candidato.score = resultado["score"]

    db.session.commit()

    return jsonify(resultado)