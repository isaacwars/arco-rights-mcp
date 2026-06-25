"""Input validation guards for ARCO MCP tools.

State-of-the-art approach: every tool handler validates its input
before processing. Errors include actionable guidance telling the
LLM exactly which tool to use for each input type.

This prevents LLMs from passing draft text to JSON tools and vice versa,
which is the #1 hallucination vector in MCP-based legal assistants.
"""

from __future__ import annotations

import json
import re
from typing import Any

_CASE_JSON_TEMPLATE = """{
  "titular": {"nombre_completo": "", "identificacion": {"tipo":"INE","vigente":true,"se_adjunta_copia":true}},
  "solicitud": {"ciudad": "", "fecha": ""},
  "medio_notificaciones": {"tipo":"correo electronico","valor":""},
  "responsable": {"naturaleza":"privado","nombre_legal":"","domicilio":"","canal_arco":"",
    "fuente_aviso_privacidad":{"tipo":"URL oficial","referencia":"","fecha_consulta":"","es_fuente_oficial":true}},
  "relacion_juridica": {"tipo":"cliente","descripcion":""},
  "datos_personales": [{"descripcion":"","categoria":"identificacion","sensible":false}],
  "derechos_solicitados": [{"tipo":"acceso","peticion_concreta":""}],
  "anexos": []
}"""


def require_case_json(value: Any, tool_name: str) -> dict[str, Any]:
    """Validate and parse case_json input for tools that expect it.

    Returns the parsed case dict. Raises ValueError with actionable
    guidance if the input is not valid JSON or is the wrong type.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"ERROR: {tool_name} espera 'case_json' (string JSON). "
            f"Recibio {type(value).__name__}. "
            "Convierte el caso a JSON string antes de pasarlo."
        )

    stripped = value.strip()

    # Early detection: draft text vs JSON
    if not stripped.startswith("{"):
        draft_markers = [
            "asunto:", "presente.", "a la atencion", "puebla",
            "comparezco", "solicito", "apercibo", "atentamente",
        ]
        if any(marker in stripped.lower() for marker in draft_markers):
            raise ValueError(
                f"ERROR CRITICO: {tool_name} recibio TEXTO DE BORRADOR en lugar de JSON. "
                "Para auditar un borrador usa 'audit_draft' (recibe draft_text). "
                "Para crear un caso JSON, CARGA PRIMERO el recurso arco://case/example "
                "que contiene la estructura exacta con TODOS los campos requeridos. "
                "NO inventes la estructura — usa la del recurso."
            )
        raise ValueError(
            f"ERROR: {tool_name} necesita un JSON que empiece con '{{'. "
            f"Recibio: '{stripped[:80]}...'. "
            "CARGA arco://case/example para ver la estructura exacta."
        )

    if len(stripped) > 5_000_000:
        raise ValueError(f"ERROR: JSON demasiado grande (max 5 MB).")

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"ERROR: JSON invalido en {tool_name}: {exc}. "
            "Verifica comillas, comas y llaves. "
            "CARGA arco://case/example para ver la estructura exacta que necesitas."
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"ERROR: {tool_name} espera un objeto JSON ({{}}), no un array ([]). "
            "El caso ARCO es un objeto con campos 'titular', 'responsable', etc. "
            "CARGA arco://case/example para ver la estructura exacta."
        )

    # Detect "invented" JSON structures — common LLM error
    known_top_keys = {
        "titular", "solicitud", "medio_notificaciones", "responsable",
        "relacion_juridica", "datos_personales", "derechos_solicitados",
        "anexos",
    }
    optional_top_keys = {"transferencias"}
    actual_keys = set(parsed.keys())
    unknown_keys = actual_keys - known_top_keys - optional_top_keys
    missing_core = known_top_keys - actual_keys

    # LLM invented field names → immediate rejection
    if unknown_keys:
        raise ValueError(
            f"ERROR CRITICO: {tool_name} — campos INVENTADOS detectados: {sorted(unknown_keys)}.\n"
            f"Los unicos campos validos en el nivel raiz son: {sorted(known_top_keys)}.\n"
            "NO inventes nombres como 'derechos', 'descripcion_solicitud', 'razon_social', etc.\n"
            "CARGA arco://case/example AHORA. Usa EXACTAMENTE los nombres del ejemplo.\n\n"
            "Ejemplo de estructura correcta:\n" + _CASE_JSON_TEMPLATE
        )

    # Type validation: critical fields must be dicts/arrays, not strings
    type_errors: list[str] = []
    for key in ("titular", "responsable", "solicitud", "medio_notificaciones"):
        if key in parsed and not isinstance(parsed[key], dict):
            type_errors.append(
                f"'{key}' debe ser un objeto ({{}}), no {type(parsed[key]).__name__} "
                f"(recibiste: '{str(parsed[key])[:60]}')"
            )
    if "datos_personales" in parsed and not isinstance(parsed["datos_personales"], list):
        type_errors.append("'datos_personales' debe ser un array ([])")
    if "derechos_solicitados" in parsed and not isinstance(parsed["derechos_solicitados"], list):
        type_errors.append("'derechos_solicitados' debe ser un array ([])")

    if type_errors:
        raise ValueError(
            f"ERROR CRITICO: {tool_name} — tipos de campo INCORRECTOS:\n" +
            "\n".join(f"  • {e}" for e in type_errors) +
            "\n\nCARGA arco://case/example para ver los tipos EXACTOS de cada campo."
        )

    # Missing mandatory fields
    if missing_core:
        raise ValueError(
            f"ERROR: {tool_name} — faltan campos obligatorios: {sorted(missing_core)}.\n"
            f"Campos presentes: {sorted(actual_keys)}.\n"
            "CARGA arco://case/example para ver TODOS los campos requeridos.\n\n"
            "Ejemplo de estructura correcta:\n" + _CASE_JSON_TEMPLATE
        )

    return parsed


def require_draft_text(value: Any, tool_name: str) -> str:
    """Validate draft_text input for tools that expect it.

    Returns the draft text. Raises ValueError if input looks like JSON.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"ERROR: {tool_name} espera 'draft_text' (texto del borrador). "
            f"Recibio {type(value).__name__}."
        )

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"ERROR: {tool_name} — draft_text no puede estar vacio.")

    # Check if user accidentally passed JSON instead of draft text
    if stripped.startswith("{") and len(stripped) < 5000:
        try:
            json.loads(stripped)
            raise ValueError(
                f"ERROR: {tool_name} recibio JSON en lugar de texto de borrador. "
                "Para validar un caso usa 'validate_case' o 'process_case' (reciben case_json). "
                "'audit_draft' y 'audit_argumentation' esperan el TEXTO LITERAL del borrador ARCO."
            )
        except json.JSONDecodeError:
            pass

    return stripped


def require_fecha_iso(value: Any, param_name: str) -> str:
    """Validate an ISO date string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"ERROR: {param_name} debe ser una fecha ISO YYYY-MM-DD. Recibio: {value}"
        )
    stripped = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", stripped):
        raise ValueError(
            f"ERROR: {param_name} — formato invalido '{stripped}'. Use ISO YYYY-MM-DD."
        )
    return stripped


def tool_error(tool_name: str, message: str) -> dict[str, Any]:
    """Standardized error response for all tools.

    IMPORTANT: This response includes EXPLICIT instructions that the LLM
    must read and act on. The LLM SHOULD NOT ignore or skip these errors.
    """
    return {
        "ok": False,
        "error": message,
        "tool": tool_name,
        "ACCION_REQUERIDA": (
            "NO IGNORES ESTE ERROR. Para corregirlo:\n"
            "1. CARGA arco://case/example para ver la estructura JSON exacta.\n"
            "2. CARGA arco://workflow/pipeline para ver el flujo correcto.\n"
            "3. Si el JSON es invalido, reconstruyelo usando los nombres EXACTOS del ejemplo.\n"
            "4. Si te faltan datos del usuario (nombre, correo, etc.), PREGUNTASELOS.\n"
            "5. NO inventes campos ni uses atajos. Sigue el pipeline."
        ),
        "legal_framework": (
            "LFPDPPP decreto 20-mar-2025. Autoridad: "
            "Secretaria Anticorrupcion y Buen Gobierno."
        ),
    }
