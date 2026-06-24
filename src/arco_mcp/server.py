"""MCP server for ARCO rights drafting."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal local envs.
    FastMCP = None  # type: ignore[assignment]

from .engine import (
    article_bundle,
    assess_case,
    audit_argumentation,
    audit_existing_draft,
    audit_responsable_identity,
    audit_source_provenance,
    build_timeline,
    build_argument_map,
    draft_arco_request,
    process_case,
    select_legal_basis,
    select_escalation_basis,
    validate_arco_case,
)
from .guards import require_case_json, require_draft_text, tool_error
from .law import EXTERNAL_LEGAL_TECH_LEARNINGS, RECENT_ARCO_REFERENCE_NOTES, SOURCE_PROVENANCE_RULES
from . import __version__


SYSTEM_PROMPT = ""


CHECKLIST = {
    "critical_before_drafting": [
        "responsable.nombre_legal desde aviso de privacidad vigente",
        "responsable.canal_arco oficial",
        "responsable.fuente_aviso_privacidad oficial, fechada y reciente",
        "titular.nombre_completo",
        "titular.identificacion vigente y adjunta",
        "medio_notificaciones",
        "relacion_juridica.descripcion",
        "datos_personales",
        "derechos_solicitados",
        "causa legitima, situacion especifica y dano/perjuicio si hay oposicion",
    ],
    "common_rejection_vectors": [
        "solicitud dirigida a sucursal y no al responsable legal",
        "nombre comercial usado como razon social",
        "canal de recepcion no previsto en aviso de privacidad",
        "identidad o representacion no acreditada",
        "oposicion sin causa legitima",
        "cancelacion como borrado inmediato absoluto",
        "rectificacion sin documento soporte",
        "articulos citados fuera de alcance",
        "autoridad incorrecta",
        "fuente de terceros usada como aviso de privacidad",
        "aviso consultado hace mas de 180 dias",
        "multas presentadas como automaticas",
    ],
    "critical_before_escalation": [
        "acuse o constancia de recepcion de la solicitud ARCO por el responsable",
        "fecha cierta de recepcion para computo de plazos",
        "respuesta del responsable o constancia de falta de respuesta",
        "fundamento especifico de la LFPDPPP vulnerado",
        "prueba_envio.acuse_o_folio si etapa es escalamiento_secretaria",
    ],
    "critical_before_amparo": [
        "notificacion formal de la resolucion de la Secretaria (LFPA arts. 35, 38, 39)",
        "plazo de 15 dias habiles no vencido (arts. 17 y 19 Ley de Amparo)",
        "definitividad verificada: no hay recurso administrativo pendiente que pueda suspender (art. 61-XX LA)",
        "acto reclamado claramente identificado (resolucion de la Secretaria)",
        "derechos humanos violados especificados (art. 16 constitucional, art. 1 principio pro persona)",
        "via correcta: amparo indirecto ante Juzgado de Distrito (arts. 107 LA, 51 LFPDPPP)",
        "suspension solicitada con argumentacion de no perjuicio al interes social (arts. 125, 128 LA)",
    ],
}

EXTERNAL_RESEARCH = {
    "source_rules": SOURCE_PROVENANCE_RULES,
    "github_learnings": EXTERNAL_LEGAL_TECH_LEARNINGS,
    "recent_arco_reference_notes": RECENT_ARCO_REFERENCE_NOTES,
    "use_policy": "Estas referencias son controles de diseno y comparacion. No sustituyen el decreto ni el aviso de privacidad oficial del responsable.",
}

PIPELINE = """PIPELINE ARCO — sigue este orden exacto. No saltes pasos.

1. source_audit(case_json)  → ¿fuente del aviso oficial y fresca? Si no, reporta blockers.
2. validate_case(case_json) → ¿caso listo? Si ready_to_draft=false, muestra missing/blockers. No redactes.
3. select_basis(case_json)  → artículos aplicables. Opcional si el caso es simple.
4. argument_map(case_json)  → mapa por derecho: alcance, límites, prueba, controles de rechazo.
5. draft_request(case_json) → solo si ready_to_draft=true. Devuelve el texto final.
6. audit_draft(draft_text)  → revisa el borrador contra patrones de error conocidos.
7. deadline_timeline(fecha) → plazos. Agrega fecha_notificacion_secretaria si hay fase de amparo.

Atajo: usa process_case(case_json) para ejecutar pasos 1-5 en una sola llamada.

Escalamiento:
- escalation_basis(etapa="escalamiento_secretaria") → fundamento LFPDPPP + LFPA
- escalation_basis(etapa="amparo") → + Ley de Amparo + Constitución

Reglas: si hay placeholders, NO redactes. Si salud/biometría sin sensible=true, BLOQUEA.
Si oposición sin daño concreto, BLOQUEA. Si >180d sin aviso reconsultado, ADVIERTE.
Nunca cites INAI/IFAI/PRODATOS. Usa Secretaría Anticorrupción y Buen Gobierno."""

STYLE_GUIDE = """GUÍA DE REDACCIÓN JURÍDICA MEXICANA — ESTILO ÉLITE

Fundamento académico: Graciela Fernández Ruiz, "Argumentación y Lenguaje
Jurídico. Aplicación al análisis de una sentencia de la SCJN", 2ª ed.,
UNAM-IIJ, México, 2017 (ISBN 978-607-02-9678-9). La autora distingue:
- Justificación interna: la conclusión debe seguirse lógicamente de las premisas
  (silogismo jurídico: norma + hecho = conclusión).
- Justificación externa: demostrar la corrección de las premisas mediante formas
  de argumento (analogía, a fortiori, a contrario).
El método CRAC es la aplicación práctica de esta dualidad.

Respaldo adicional: Jorge F. Malem Seña, "El lenguaje de las sentencias",
Reforma Judicial. Revista Mexicana de Justicia, IIJ-UNAM, núm. 7, 2006,
pp. 47-60. Identifica los vicios forenses que esta guía combate: gerundios
concatenados, pasiva con "se" agentiva, frases desmesuradamente largas,
nominalizaciones excesivas, siglas sin expandir y copia mecánica de fórmulas
legislativas. Las 4 reglas de oro derivan directamente de este diagnóstico.

Usa esta guía para refinar borradores ARCO. Aplícala después de pasar audit_draft.

═══ MÉTODO CRAC (Conclusión → Regla → Aplicación → Conclusión) ═══

CRAC no es un método anglosajón adaptado. Es la estructura NATIVA del
razonamiento judicial mexicano. La SCJN la ha usado por décadas en sus
sentencias (Fernández Ruiz documenta su aplicación desde al menos 2006
en el Amparo en Revisión 02352/1997-00). Las firmas corporativas solo le
pusieron nombre comercial. La estructura SCJN es:

  Resultandos → hechos del caso
  Considerandos → cada uno contiene: [C] tesis + [R] norma + [A] subsunción
  Resolutivos → [C] conclusión final: se concede/niega

Estructura cada petición o sección del escrito en 4 bloques:

  I. CONCLUSIÓN INICIAL (Tesis). Primera línea: qué vas a demostrar o qué exiges.
     Sin preámbulos. Ej: "La cancelación es improcedente por obligación legal."

  II. REGLA (Fundamento). Cita el artículo exacto y transcribe solo lo esencial.
     Ej: "El artículo 26, fracción V, de la Ley establece que no procede cancelar
     cuando el tratamiento sea necesario para cumplir una obligación legal."

  III. APLICACIÓN (Subsunción). Conecta la regla con los hechos concretos.
     Ej: "En el presente caso, el solicitante fue cliente de esta institución
     financiera. El artículo 115 de la Ley de Instituciones de Crédito obliga
     a conservar el expediente por 10 años."

  IV. CONCLUSIÓN FINAL (Petición concreta). Cierra reiterando el efecto jurídico.
     Ej: "Por tanto, solicito se declare justificada la negativa de cancelación."

═══ REGLA DE ORO 0: LO DICHO vs LO IMPLICADO ═══

Basado en Paul Grice (Studies in the Way of Words, 1989), analizado por
Fernández Ruiz (2017, Cap. VI). En el discurso jurídico mexicano, el juez
o autoridad SÓLO puede pronunciarse sobre lo EXPLÍCITAMENTE solicitado.
Lo meramente implicado o sugerido NO vincula ni obliga a la autoridad.

En cada petición del escrito, verifica:
- ¿Está EXPLÍCITA la petición concreta? (no basta sugerirla)
- ¿Está EXPLÍCITO el artículo que la fundamenta? (no basta mencionarlo de paso)
- ¿Está EXPLÍCITA la consecuencia jurídica que se pide? (no basta describir el problema)

Ejemplo de lo DICHO vs lo IMPLICADO en una solicitud ARCO:
  IMPLICADO (débil): "Me preocupa el uso de mis datos para mercadotecnia."
  DICHO (fuerte):   "Solicito el cese del tratamiento de mis datos para
                     finalidades de mercadotecnia, con fundamento en el
                     artículo 26, fracción I, de la Ley."

═══ 4 REGLAS DE ORO ═══

1. PÁRRAFOS DE 5 LÍNEAS MÁXIMO.
   Si un párrafo supera 5-6 líneas, divídelo. El espacio en blanco ayuda al lector.

2. VOZ ACTIVA (Sujeto → Verbo → Predicado).
   ❌ "El aviso de privacidad fue firmado por el titular."
   ✅ "El titular firmó el aviso de privacidad."

3. GERUNDIO: SOLO SIMULTANEIDAD. NUNCA POSTERIORIDAD NI ADJETIVAL.
   El gerundio (-ando, -iendo) es el vicio forense más común y peligroso
   (Malem Seña dedica un apartado entero a documentarlo). Hay 4 tipos:

   ✅ SIMULTANEIDAD (válido): acción ocurre AL MISMO TIEMPO que el verbo principal.
      "El titular firmó el aviso aceptando los términos."
      "Comparezco señalando como medio para notificaciones el correo."
      Riesgo legal: NINGUNO. Es el único uso correcto.

   ❌ POSTERIORIDAD (nulidad procesal): acción ocurre DESPUÉS del verbo principal.
      "Se celebró el contrato, firmando las partes al calce."
      Riesgo legal: AMBIGÜEDAD TEMPORAL. ¿Firmaron mientras se celebraba o después?
      La contraparte puede alegar error en la secuencia de hechos → anulable.

   ❌ ADJETIVAL (sin fuerza normativa): gerundio usado como adjetivo calificativo.
      "La ley estableciendo los derechos" en vez de "la ley que establece".
      "El decreto reformando el artículo 31" en vez de "el decreto que reforma".
      Riesgo legal: El gerundio NO tiene fuerza declarativa en español jurídico.
      Un juez puede interpretarlo como NO VINCULANTE. Lo que está en gerundio
      no obliga; solo lo que está en indicativo o imperativo tiene fuerza legal.

   ❌ GERUNDIO DEL BOE/DOF (arcaísmo administrativo): heredado de la admin pública.
      "El oficio de fecha 23 de junio, reformando el acuerdo anterior."
      Riesgo legal: Aunque es ubicuo en oficios, es impreciso y debilita el texto.

   REGLA PRÁCTICA: Reemplaza TODO gerundio por "que + verbo conjugado" o "y + verbo".
   ❌ "Decreto reformando la ley"  →  ✅ "Decreto que reforma la ley"
   ❌ "firmando las partes"         →  ✅ "y las partes firmaron"
   ❌ "El oficio estableciendo"     →  ✅ "El oficio que establece"

4. SUBTÍTULOS COMO MAPA DE NAVEGACIÓN.
   El escrito debe entenderse leyendo solo los títulos en negritas.
   Usa encabezados contundentes: "I. Improcedencia de la cancelación",
   "II. Cumplimiento del principio de proporcionalidad".

═══ EJEMPLO: ANTES vs DESPUÉS ═══

ESTILO TRADICIONAL (débil):
"Que por medio del presente ocurso y resultando a todas luces infundado
el dicho del solicitante, toda vez que resulta menester precisar que mi
representada se encuentra impedida para realizar la cancelación solicitada
en virtud de que de conformidad con lo que a la letra reza el artículo 26
de la LFPDPPP, existen excepciones, y en la especie, la Ley de Instituciones
de Crédito nos obliga a guardar los datos, por lo que pido se deseche su queja."

ESTILO CRAC (élite):
I. Improcedencia de la cancelación por obligación legal.
Esta empresa no es omisa; la cancelación es legalmente improcedente.
El artículo 26 de la Ley establece que no procede cancelar cuando
el tratamiento sea necesario para cumplir una obligación legal.
El solicitante fue cliente de esta institución financiera. El artículo 115
de la Ley de Instituciones de Crédito obliga a conservar el expediente
de identificación del cliente por un mínimo de 10 años.
Dado que el plazo de 10 años no ha transcurrido, esta empresa tiene
la obligación legal de conservar los datos. Solicito se declare
justificada la negativa y se sobresea la queja.

═══ CÓMO USAR ESTA GUÍA CON EL MCP ═══

1. Genera el borrador con process_case o draft_request.
2. Pasa el borrador por audit_draft para detectar errores jurídicos.
3. Corrige los errores jurídicos detectados.
4. APLICA ESTA GUÍA para refinar el estilo (párrafos cortos, CRAC, voz activa).
5. Vuelve a pasar por audit_draft para verificar que no introdujiste errores."""

LEGAL_OVERVIEW = """MODELO MENTAL DEL MARCO JURÍDICO ARCO — 4 LEYES, 1 CADENA

ESTRUCTURA: El sistema se apila en capas. Cada capa resuelve un vacío de la anterior.

CAPA 1 — LFPDPPP (ley principal, decreto 20-mar-2025)
  Rol: Define los derechos ARCO (arts. 21-26), el procedimiento ante el responsable
  (arts. 27-34) y ante la Secretaría Anticorrupción y Buen Gobierno (arts. 38-54).
  Límites: art. 3 (seguridad nacional, orden público, salud pública, derechos de terceros).
  Dato sensible: art. 8 exige consentimiento expreso y por escrito.
  Cada derecho ARCO tiene reglas específicas:
  - Acceso (art. 22): sin necesidad de describir datos. Se cumple por puesta a disposición.
  - Rectificación (arts. 23, 30): requiere documento soporte obligatorio.
  - Cancelación (arts. 24, 25): bloqueo previo + supresión posterior. Art. 25 lista excepciones.
  - Oposición (art. 26): DOS supuestos — causa legítima O tratamiento automatizado.
    NO procede si hay obligación legal. Requiere daño concreto, no genérico.
  - Limitación y revocación: NO son derechos ARCO autónomos. Son peticiones complementarias.

CAPA 2 — LFPA (supletoria, DOF 04-ago-1994, reforma 14-nov-2025)
  Rol: Llena vacíos procesales donde la LFPDPPP guarda silencio (art. 4 LFPDPPP).
  - Art. 2: supletoriedad expresa a TODAS las leyes administrativas.
  - Art. 3: requisitos del acto administrativo (fundado, motivado, por escrito, firma).
    Si la Secretaría omite alguno, su resolución es NULA (art. 6 LFPA).
  - Art. 28: días hábiles = excluye sábados, domingos, feriados listados.
  - Arts. 35-41: régimen completo de notificaciones.
    Art. 39: notificar en máx. 10 días con texto íntegro + fundamento.
    Art. 41: si no notifican o notifican mal, se impugna.
  - Art. 31: ampliación de plazos máx. 50% del original.

CAPA 3 — Ley de Amparo (DOF 02-abr-2013)
  Rol: Única vía judicial contra la resolución definitiva de la Secretaría (art. 51 LFPDPPP).
  - Art. 17: 15 DÍAS para presentar demanda.
  - Art. 19: esos 15 días son HÁBILES (excluye sábados, domingos, feriados listados).
  - Art. 107 fracs. II y III: amparo INDIRECTO (no directo). Se presenta ante Juzgado de Distrito.
  - Art. 61 frac. XX (DEFINITIVIDAD): si existe recurso administrativo que suspenda el acto
    con alcance similar al amparo, DEBE AGOTARSE primero o el amparo es improcedente.
  - Arts. 125+128: suspensión del acto. Requiere: a) que la pida el quejoso,
    b) que no perjudique interés social ni contravenga orden público.

CAPA 4 — Constitución (CPEUM)
  Rol: Fundamento último. Sin esto no hay amparo.
  - Art. 1: principio PRO PERSONA → en caso de duda, interpretación más favorable al titular.
  - Art. 16 párrafo 2: derecho constitucional a protección de datos + ARCO.
    Mismas excepciones que el art. 3 LFPDPPP (seguridad nacional, orden público, etc.).
  - Art. 103: procedencia del amparo contra actos de autoridad que violen derechos humanos.

CONEXIONES CLAVE:
  LFPDPPP art. 4 → LFPA (supletoriedad)
  LFPDPPP art. 51 → Ley de Amparo (amparo contra resoluciones de la Secretaría)
  LFPDPPP art. 3  → Constitución art. 16 (mismas excepciones: seguridad, orden, salud, terceros)
  LFPA art. 41     → Ley de Amparo art. 17 (notificación defectuosa = plazo no empieza a correr)
  LFPA art. 3      → impugnar resolución de Secretaría mal fundada/motivada
  CPEUM art. 1     → toda duda se resuelve a favor del titular

RAZONAMIENTO TÍPICO DEL LLM:
  1. "El caso tiene datos de salud no marcados sensibles" → art. 8 LFPDPPP: BLOQUEA.
  2. "La oposición tiene daño genérico 'afecta mi privacidad'" → art. 26 LFPDPPP: BLOQUEA.
  3. "La Secretaría no notificó en 10 días" → art. 39 LFPA: notificación irregular.
  4. "El plazo de amparo venció ayer" → art. 17 LA + art. 61 frac. XIV LA: IMPROCEDENTE.
  5. "Hay recurso administrativo que suspende" → art. 61 frac. XX LA: AGOTAR PRIMERO.
  6. "El responsable invoca art. 3 LFPDPPP" → exigir supuesto concreto, dato afectado, prueba."""


TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "process_case": {
        "description": "Pipeline completo: validar, fundamentar, argumentar y redactar. Usar primero. Recibe case_json (JSON del caso, NO texto).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_json": {
                    "type": "string",
                    "description": "JSON del caso. Debe empezar con '{'."
                }
            },
            "required": ["case_json"],
        },
    },
    "validate_case": {
        "description": "Audita si un caso ARCO esta listo para redactarse sin huecos legales criticos. IMPORTANTE: recibe case_json (JSON string con campos titular, responsable, datos_personales, derechos_solicitados). NO pases texto de borrador aqui.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_json": {
                    "type": "string",
                    "description": "JSON string del caso ARCO. Debe empezar con '{'. Ejemplo: '{\"titular\":{\"nombre_completo\":\"...\"},...}'"
                }
            },
            "required": ["case_json"],
        },
    },
    "audit_draft": {
        "description": "Audita un borrador ARCO (TEXTO LITERAL de la solicitud) para detectar autoridad equivocada, articulos mal usados y amenazas sancionatorias imprecisas. IMPORTANTE: recibe draft_text (texto plano del borrador). NO pases JSON aqui.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_text": {
                    "type": "string",
                    "description": "TEXTO LITERAL del borrador (no JSON). Ejemplo: 'ASUNTO: Ejercicio de Derechos ARCO...'"
                },
                "case_json": {"type": "string", "default": ""},
            },
            "required": ["draft_text"],
        },
    },
    "assess_case": {
        "description": "Valorar solidez juridica (irrefutable/solido/debil/insostenible) con implicaciones legales y pronostico. Recibe case_json.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_json": {
                    "type": "string",
                    "description": "JSON del caso."
                }
            },
            "required": ["case_json"],
        },
    },
    "audit_argumentation": {
        "description": "Audita vicios argumentativos en borradores: terminos indefinidos, logica circular, condicionales debiles, carga de prueba mal asignada, exageraciones y listas exhaustivas. Complementa a audit_draft (que revisa correccion juridica).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_text": {"type": "string", "description": "Texto del borrador."}
            },
            "required": ["draft_text"],
        },
    },
    "audit_identity": {
        "description": "Detecta riesgos de razon social incorrecta, nombre comercial, sucursal o canal ARCO no oficial.",
        "inputSchema": {
            "type": "object",
            "properties": {"case_json": {"type": "string"}},
            "required": ["case_json"],
        },
    },
    "source_audit": {
        "description": "Audita procedencia, fuente oficial, frescura del aviso de privacidad y riesgo de usar terceros como base legal.",
        "inputSchema": {
            "type": "object",
            "properties": {"case_json": {"type": "string"}},
            "required": ["case_json"],
        },
    },
    "select_basis": {
        "description": "Selecciona articulos aplicables segun derechos y hechos, sin sobrecitar.",
        "inputSchema": {
            "type": "object",
            "properties": {"case_json": {"type": "string"}},
            "required": ["case_json"],
        },
    },
    "draft_request": {
        "description": "Redacta una solicitud ARCO solo si el caso supera la validacion critica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_json": {"type": "string"},
            },
            "required": ["case_json"],
        },
    },
    "argument_map": {
        "description": "Construye mapa argumento-por-argumento: fundamento, alcance, limite legal, prueba requerida y controles de rechazo.",
        "inputSchema": {
            "type": "object",
            "properties": {"case_json": {"type": "string"}},
            "required": ["case_json"],
        },
    },
    "deadline_timeline": {
        "description": "Calcula plazos ARCO en dias habiles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fecha_recepcion": {"type": "string"},
                "fecha_respuesta": {"type": "string", "default": ""},
                "fecha_presentacion_secretaria": {"type": "string", "default": ""},
                "fecha_notificacion_secretaria": {"type": "string", "default": ""},
                "holidays_json": {"type": "string", "default": "[]"},
            },
            "required": ["fecha_recepcion"],
        },
    },
    "law_articles": {
        "description": "Devuelve matriz controlada de articulos de la LFPDPPP 2025.",
        "inputSchema": {
            "type": "object",
            "properties": {"article_numbers_json": {"type": "string", "default": "[]"}},
        },
    },
    "escalation_basis": {
        "description": "Devuelve fundamento legal completo para fase de escalamiento: LFPDPPP, LFPA, Ley de Amparo y Constitucion, segun la etapa.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "etapa": {
                    "type": "string",
                    "default": "escalamiento_secretaria",
                    "enum": ["escalamiento_secretaria", "amparo"],
                },
            },
        },
    },
}


def _call_tool(name: str, args: dict[str, Any]) -> Any:
    dispatch: dict[str, Callable[..., Any]] = {
        "validate_case": _validate_case_call,
        "audit_identity": _audit_identity_call,
        "source_audit": _source_audit_call,
        "select_basis": _select_basis_call,
        "draft_request": _draft_request_call,
        "argument_map": _argument_map_call,
        "audit_draft": _audit_draft_call,
        "deadline_timeline": _deadline_call,
        "law_articles": _law_articles_call,
        "escalation_basis": _escalation_basis_call,
        "process_case": _process_case_call,
        "assess_case": _assess_case_call,
        "audit_argumentation": _audit_argumentation_call,
    }
    if name not in dispatch:
        return tool_error(name, f"Tool desconocida: {name}")
    try:
        return dispatch[name](**args)
    except (ValueError, TypeError) as exc:
        return tool_error(name, str(exc))


def _validate_case_call(case_json: str) -> Any:
    return validate_arco_case(require_case_json(case_json, "validate_case"))


def _audit_identity_call(case_json: str) -> Any:
    return audit_responsable_identity(require_case_json(case_json, "audit_identity"))


def _source_audit_call(case_json: str) -> Any:
    return audit_source_provenance(require_case_json(case_json, "source_audit"))


def _select_basis_call(case_json: str) -> Any:
    return select_legal_basis(require_case_json(case_json, "select_basis"))


def _draft_request_call(case_json: str) -> Any:
    return draft_arco_request(require_case_json(case_json, "draft_request"))


def _argument_map_call(case_json: str) -> Any:
    return build_argument_map(require_case_json(case_json, "argument_map"))


def _audit_draft_call(draft_text: str, case_json: str = "") -> Any:
    text = require_draft_text(draft_text, "audit_draft")
    case = require_case_json(case_json, "audit_draft") if case_json.strip() else None
    return audit_existing_draft(text, case)


def _deadline_call(
    fecha_recepcion: str,
    fecha_respuesta: str = "",
    holidays_json: str = "[]",
    fecha_presentacion_secretaria: str = "",
    fecha_notificacion_secretaria: str = "",
) -> Any:
    holidays = json.loads(holidays_json) if holidays_json else []
    return build_timeline(
        fecha_recepcion,
        fecha_respuesta or None,
        holidays,
        fecha_presentacion_secretaria or None,
        fecha_notificacion_secretaria or None,
    )


def _law_articles_call(article_numbers_json: str = "[]") -> Any:
    ids = json.loads(article_numbers_json) if article_numbers_json else []
    return article_bundle(ids or None)


def _escalation_basis_call(etapa: str = "escalamiento_secretaria") -> Any:
    return select_escalation_basis(etapa)


def _process_case_call(case_json: str) -> Any:
    return process_case(require_case_json(case_json, "process_case"))


def _assess_case_call(case_json: str) -> Any:
    return assess_case(require_case_json(case_json, "assess_case"))


def _audit_argumentation_call(draft_text: str) -> Any:
    return audit_argumentation(require_draft_text(draft_text, "audit_argumentation"))


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


if FastMCP is not None:
    mcp = FastMCP(
        "arco-rights",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
    )

    @mcp.tool()
    def validate_case(case_json: str) -> str:
        """Audita si un caso ARCO esta listo para redactarse sin huecos legales criticos.

        Args:
            case_json: JSON del caso con titular, responsable, relacion juridica,
                datos personales, derechos solicitados y anexos.
        """
        return _json(_validate_case_call(case_json))

    @mcp.tool()
    def audit_identity(case_json: str) -> str:
        """Detecta riesgos de responsable incorrecto, nombre comercial, sucursal o canal ARCO no oficial.

        Args:
            case_json: JSON del caso o al menos objeto con responsable y relacion_juridica.
        """
        return _json(_audit_identity_call(case_json))

    @mcp.tool()
    def source_audit(case_json: str) -> str:
        """Audita procedencia, fuente oficial y frescura del aviso de privacidad.

        Args:
            case_json: JSON del caso o al menos objeto con responsable.fuente_aviso_privacidad.
        """
        return _json(_source_audit_call(case_json))

    @mcp.tool()
    def select_basis(case_json: str) -> str:
        """Selecciona articulos aplicables sin sobrecitar ni usar articulos fuera de alcance.

        Args:
            case_json: JSON del caso.
        """
        return _json(_select_basis_call(case_json))

    @mcp.tool()
    def draft_request(case_json: str) -> str:
        """Redacta una solicitud ARCO solo si el caso supera la validacion critica.

        Args:
            case_json: JSON del caso.
        """
        return _json(_draft_request_call(case_json))

    @mcp.tool()
    def argument_map(case_json: str) -> str:
        """Construye mapa de argumentos y limites legales antes de redactar.

        Args:
            case_json: JSON del caso.
        """
        return _json(_argument_map_call(case_json))

    @mcp.tool()
    def audit_draft(draft_text: str, case_json: str = "") -> str:
        """Audita un borrador ARCO para detectar autoridad equivocada, articulos mal usados y amenazas sancionatorias imprecisas.

        Args:
            draft_text: Texto del borrador.
            case_json: JSON opcional del caso relacionado.
        """
        return _json(_audit_draft_call(draft_text, case_json))

    @mcp.tool()
    def deadline_timeline(
        fecha_recepcion: str,
        fecha_respuesta: str = "",
        holidays_json: str = "[]",
        fecha_presentacion_secretaria: str = "",
        fecha_notificacion_secretaria: str = "",
    ) -> str:
        """Calcula plazos ARCO en dias habiles.

        Args:
            fecha_recepcion: Fecha ISO YYYY-MM-DD de recepcion por el responsable.
            fecha_respuesta: Fecha ISO opcional de respuesta del responsable.
            holidays_json: JSON array opcional con feriados ISO YYYY-MM-DD.
            fecha_presentacion_secretaria: Fecha ISO opcional de solicitud de proteccion ante Secretaria.
            fecha_notificacion_secretaria: Fecha ISO opcional de notificacion de la resolucion de la Secretaria.
        """
        return _json(_deadline_call(fecha_recepcion, fecha_respuesta, holidays_json, fecha_presentacion_secretaria, fecha_notificacion_secretaria))

    @mcp.tool()
    def law_articles(article_numbers_json: str = "[]") -> str:
        """Devuelve matriz controlada de articulos de la LFPDPPP 2025.

        Args:
            article_numbers_json: JSON array opcional, por ejemplo ["21", "28", "31"].
        """
        return _json(_law_articles_call(article_numbers_json))

    @mcp.tool()
    def escalation_basis(etapa: str = "escalamiento_secretaria") -> str:
        """Fundamento legal completo para fase de escalamiento: LFPDPPP + LFPA + Ley de Amparo + Constitucion.

        Args:
            etapa: 'escalamiento_secretaria' incluye LFPDPPP + LFPA. 'amparo' incluye ademas Ley de Amparo + Constitucion.
        """
        return _json(_escalation_basis_call(etapa))

    @mcp.tool()
    def process_case(case_json: str) -> str:
        """Pipeline ARCO completo en una sola llamada. Corre validate, basis, argument_map y draft.
        Si el caso no esta listo, draft saldra null; revisa validation.missing y validation.blockers.
        No necesitas llamar validate_case, select_basis, argument_map ni draft_request por separado.
        """
        return _json(_process_case_call(case_json))

    @mcp.tool()
    def assess_case(case_json: str) -> str:
        """Valoracion juridica estructurada del caso ARCO. Evalua el nivel de solidez
        (irrefutable, solido, solido_con_reservas, incompleto, debil, insostenible),
        las implicaciones legales de cada hallazgo y emite un pronostico de viabilidad.
        Usala para saber si el caso resistiria un escrutinio legal serio.
        """
        return _json(_assess_case_call(case_json))

    @mcp.tool()
    def audit_argumentation(draft_text: str) -> str:
        """Audita vicios argumentativos en un borrador ARCO. Detecta terminos indefinidos,
        logica circular, condicionales debiles, carga de prueba mal asignada, exageraciones,
        listas exhaustivas, vacios referenciales e inconsistencias de fundamentos.
        Complementa a audit_draft: este revisa calidad argumentativa, aquel revisa correccion juridica.
        """
        return _json(_audit_argumentation_call(draft_text))

    @mcp.resource(
        "arco://prompt/system",
        name="system_prompt",
        description="Prompt maestro anti-alucinacion para solicitudes ARCO.",
        mime_type="text/plain",
    )
    def resource_system_prompt() -> str:
        return SYSTEM_PROMPT

    @mcp.resource(
        "arco://law/matrix",
        name="law_matrix",
        description="Matriz controlada de articulos de la LFPDPPP 2025.",
        mime_type="application/json",
    )
    def resource_law_matrix() -> str:
        return _json(article_bundle())

    @mcp.resource(
        "arco://workflow/checklist",
        name="drafting_checklist",
        description="Checklist de bloqueadores y vectores comunes de rechazo.",
        mime_type="application/json",
    )
    def resource_checklist() -> str:
        return _json(CHECKLIST)

    @mcp.resource(
        "arco://research/external-learnings",
        name="external_research_learnings",
        description="Aprendizajes de repos legales mexicanos y referencias ARCO recientes usados como controles anti-alucinacion.",
        mime_type="application/json",
    )
    def resource_external_research() -> str:
        return _json(EXTERNAL_RESEARCH)

    @mcp.resource(
        "arco://workflow/pipeline",
        name="pipeline",
        description="Receta paso a paso del flujo ARCO. Cargala si no sabes por donde empezar.",
        mime_type="text/plain",
    )
    def resource_pipeline() -> str:
        return PIPELINE

    @mcp.resource(
        "arco://law/overview",
        name="legal_overview",
        description="Modelo mental del marco juridico: como se conectan LFPDPPP, LFPA, Ley de Amparo y Constitucion. Carga esto PRIMERO para entender el sistema.",
        mime_type="text/plain",
    )
    def resource_legal_overview() -> str:
        return LEGAL_OVERVIEW

    @mcp.resource(
        "arco://writing/style",
        name="writing_style_guide",
        description="Guia de redaccion juridica mexicana: metodo CRAC, reglas de oro y ejemplos. Cargala para refinar el estilo de borradores.",
        mime_type="text/plain",
    )
    def resource_style_guide() -> str:
        return STYLE_GUIDE

else:
    mcp = None


def _write_response(message: dict[str, Any]) -> None:
    try:
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except BrokenPipeError:
        pass


def _rpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _minimal_stdio_server() -> None:
    """Dependency-free MCP stdio server for environments without the SDK."""
    resources = [
        {
            "uri": "arco://prompt/system",
            "name": "system_prompt",
            "description": "Prompt maestro anti-alucinacion para solicitudes ARCO.",
            "mimeType": "text/plain",
        },
        {
            "uri": "arco://law/matrix",
            "name": "law_matrix",
            "description": "Matriz controlada de articulos de la LFPDPPP 2025.",
            "mimeType": "application/json",
        },
        {
            "uri": "arco://workflow/checklist",
            "name": "drafting_checklist",
            "description": "Checklist de bloqueadores y vectores comunes de rechazo.",
            "mimeType": "application/json",
        },
        {
            "uri": "arco://research/external-learnings",
            "name": "external_research_learnings",
            "description": "Aprendizajes de repos legales mexicanos y referencias ARCO recientes usados como controles anti-alucinacion.",
            "mimeType": "application/json",
        },
        {
            "uri": "arco://workflow/pipeline",
            "name": "pipeline",
            "description": "Receta paso a paso del flujo ARCO. Cargala si no sabes por donde empezar.",
            "mimeType": "text/plain",
        },
        {
            "uri": "arco://law/overview",
            "name": "legal_overview",
            "description": "Modelo mental del marco juridico: como se conectan LFPDPPP, LFPA, Ley de Amparo y Constitucion.",
            "mimeType": "text/plain",
        },
        {
            "uri": "arco://writing/style",
            "name": "writing_style_guide",
            "description": "Guia de redaccion juridica mexicana: metodo CRAC y reglas de oro.",
            "mimeType": "text/plain",
        },
    ]
    resource_data = {
        "arco://prompt/system": ("text/plain", SYSTEM_PROMPT),
        "arco://law/matrix": ("application/json", _json(article_bundle())),
        "arco://workflow/checklist": ("application/json", _json(CHECKLIST)),
        "arco://research/external-learnings": ("application/json", _json(EXTERNAL_RESEARCH)),
        "arco://workflow/pipeline": ("text/plain", PIPELINE),
        "arco://law/overview": ("text/plain", LEGAL_OVERVIEW),
        "arco://writing/style": ("text/plain", STYLE_GUIDE),
    }

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _write_response(_rpc_error(None, -32700, "Parse error"))
            continue

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if request_id is None and method and method.startswith("notifications/"):
            continue

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": "arco-rights", "version": __version__},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {"name": name, **definition}
                        for name, definition in TOOL_DEFINITIONS.items()
                    ]
                }
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                payload = _call_tool(name, arguments)
                result = {
                    "content": [{"type": "text", "text": _json(payload)}],
                    "isError": False,
                }
            elif method == "resources/list":
                result = {"resources": resources}
            elif method == "resources/read":
                uri = params.get("uri")
                if uri not in resource_data:
                    raise ValueError(f"Resource desconocido: {uri}")
                mime, text = resource_data[uri]
                result = {"contents": [{"uri": uri, "mimeType": mime, "text": text}]}
            else:
                _write_response(_rpc_error(request_id, -32601, f"Metodo no soportado: {method}"))
                continue
            _write_response(_rpc_result(request_id, result))
        except Exception as exc:  # noqa: BLE001 - RPC boundary.
            _write_response(_rpc_result(request_id, tool_error(
                params.get("name", "unknown"),
                str(exc)
            )))


def main() -> None:
    parser = argparse.ArgumentParser(description="ARCO Rights MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8000")))
    args, _ = parser.parse_known_args()

    if mcp is None:
        if args.transport != "stdio":
            print("HTTP/SSE transports require installing the optional 'fastmcp' extra.", file=sys.stderr)
            raise SystemExit(2)
        _minimal_stdio_server()
        return

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
