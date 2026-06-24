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


def require_case_json(value: Any, tool_name: str) -> dict[str, Any]:
    """Validate and parse case_json input for tools that expect it.

    Returns the parsed case dict. Raises ValueError with actionable
    guidance if the input is not valid JSON or is the wrong type.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"{tool_name}: espera 'case_json' (string JSON). "
            f"Recibio {type(value).__name__}. "
            "Convierte el caso a JSON string antes de pasarlo."
        )

    stripped = value.strip()

    # Early detection: draft text vs JSON
    if not stripped.startswith("{"):
        # Check if it looks like a draft (Spanish legal text)
        draft_markers = [
            "asunto:", "presente.", "a la atenciÓn", "puebla",
            "comparezco", "solicito", "apercibo", "atentamente",
        ]
        if any(marker in stripped.lower() for marker in draft_markers):
            raise ValueError(
                f"{tool_name}: recibiste TEXTO DE BORRADOR en lugar de JSON de caso. "
                "Para auditar un borrador usa 'audit_draft' (recibe draft_text, no case_json). "
                "Para validar/valorar un caso, construye un JSON estructurado con campos como "
                "'titular', 'responsable', 'datos_personales', 'derechos_solicitados'. "
                "Usa el schema en schema_solicitud_arco.json como referencia."
            )
        raise ValueError(
            f"{tool_name}: case_json debe ser un string JSON que empiece con '{{'. "
            f"Recibio: '{stripped[:80]}...'. "
            "Si estas enviando un borrador, usa la herramienta 'audit_draft' en su lugar."
        )

    if len(stripped) > 5_000_000:
        raise ValueError(f"{tool_name}: JSON demasiado grande (max 5 MB).")

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{tool_name}: JSON invalido: {exc}. "
            "Verifica que el JSON este bien formado (comillas, comas, llaves)."
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"{tool_name}: el JSON debe ser un objeto ({{}}), no un array ([]). "
            "El caso ARCO se representa como un objeto con campos 'titular', "
            "'responsable', etc."
        )

    return parsed


def require_draft_text(value: Any, tool_name: str) -> str:
    """Validate draft_text input for tools that expect it.

    Returns the draft text. Raises ValueError if input looks like JSON.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"{tool_name}: espera 'draft_text' (string con el texto del borrador). "
            f"Recibio {type(value).__name__}."
        )

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{tool_name}: draft_text no puede estar vacio.")

    # Check if user accidentally passed JSON instead of draft text
    if stripped.startswith("{") and len(stripped) < 5000:
        try:
            json.loads(stripped)
            raise ValueError(
                f"{tool_name}: recibiste JSON en lugar de texto de borrador. "
                "Para validar un caso usa 'validate_case' o 'process_case' (reciben case_json). "
                "'audit_draft' espera el TEXTO LITERAL de la solicitud ARCO redactada."
            )
        except json.JSONDecodeError:
            pass  # Not valid JSON, just a coincidence — let it through

    return stripped


def require_fecha_iso(value: Any, param_name: str) -> str:
    """Validate an ISO date string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{param_name}: debe ser una fecha ISO YYYY-MM-DD. Recibio: {value}"
        )
    stripped = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", stripped):
        raise ValueError(
            f"{param_name}: formato invalido '{stripped}'. Use ISO YYYY-MM-DD."
        )
    return stripped


def tool_error(tool_name: str, message: str) -> dict[str, Any]:
    """Standardized error response for all tools."""
    return {
        "ok": False,
        "error": message,
        "tool": tool_name,
        "guidance": (
            "Consulta arco://workflow/pipeline para el flujo correcto "
            "o arco://law/overview para el marco juridico."
        ),
        "legal_framework": (
            "LFPDPPP decreto 20-mar-2025. Autoridad: "
            "Secretaria Anticorrupcion y Buen Gobierno."
        ),
    }
