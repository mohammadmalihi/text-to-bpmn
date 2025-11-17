import os
from flask import Blueprint, jsonify, render_template, request, send_from_directory

from .converter import convert_text_to_bpmn

bp = Blueprint("main", __name__)


@bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@bp.route("/convert", methods=["POST"])
def convert():
    payload = request.get_json(silent=True) or {}
    user_text = (payload.get("text") or "").strip()

    if not user_text:
        return (
            jsonify(
                {
                    "error": "متنی وارد نشده است. لطفاً یک شرح فرایند وارد کنید.",
                }
            ),
            400,
        )

    try:
        diagram = convert_text_to_bpmn(user_text)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"bpmn": diagram})


# Serve guided tour assets placed under project 'assets' directory
@bp.route("/assets/<path:filename>")
def serve_assets(filename: str):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    assets_dir = os.path.join(base_dir, "assets")
    return send_from_directory(assets_dir, filename)






