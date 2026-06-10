from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)


@api_bp.route('/')
def index():
    return jsonify({"status": "ok", "version": "1.0"})
