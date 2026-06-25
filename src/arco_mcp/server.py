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
    community_detail,
    counter_defenses,
    draft_arco_request,
    legal_graph,
    process_case,
    select_legal_basis,
    select_escalation_basis,
    semantic_search,
    validate_arco_case,
)
from .guards import require_case_json, require_draft_text, tool_error
from .law import EXTERNAL_LEGAL_TECH_LEARNINGS, RECENT_ARCO_REFERENCE_NOTES, REGULATION_ARTICLES, SOURCE_PROVENANCE_RULES
from . import __version__


SYSTEM_PROMPT = """ARCO MCP arco-rights v0.3. Carga arco://case/example y arco://writing/style antes de usar tools. Si process_case devuelve ready_to_draft=false, PREGUNTA al usuario — NO entregues draft_preview.

Todo texto que produzcas DEBE cumplir estas reglas. No son sugerencias. Son requisitos. El audit_argumentation rechazara el texto si las violas.

1. CRAC: Conclusión → Regla (articulo exacto) → Aplicación (hechos) → Conclusión. 4 bloques por peticion.
2. LO DICHO vs LO IMPLICADO: Solo lo explicito obliga. Cada peticion DEBE declarar derecho, articulo y consecuencia. Nada sugerido.
3. ARGUMENTO NECESARIO: Norma + Hecho = Conclusión. Si la conclusion no se sigue NECESARIAMENTE, es debil.
4. CARGA DE LA PRUEBA: Quien alega, prueba. NUNCA "salvo que no sean" — siempre "salvo que el responsable acredite".
5. PARRAFOS 5 LINEAS MAX. Voz activa (sujeto → verbo → predicado). Gerundio SOLO simultaneidad.
6. ENTIMEMA: No expliques la ley a la empresa. Solo citala. "Art. 28 exige X" — nunca "El art. 28, que regula los requisitos..."
7. ECONOMIA: Si una oracion no avanza el argumento, BORRALA. Cada palabra gana terreno juridico.
8. VERDAD LITERAL: Solo lo literal obliga. Si admite dos interpretaciones, la contraparte usara la que te perjudica.
9. MAXIMA DE CANTIDAD: No des info de mas, pero tampoco de menos. Lo que OMITES puede inferirse en tu contra. Si dices "datos de ubicacion" sin especificar "GPS, BTS y WiFi", la empresa borrara solo lo que le convenga.
10. IMPLICATURA NO CANCELABLE: "Incluso", "ni siquiera", "pero" crean inferencias legales que NO puedes deshacer. "Transferencia, incluso a afiliadas" implica que afiliadas es el caso extremo. Usalas solo si buscas ese efecto.
11. ACTO DE HABLA: "Exijo" ≠ "Solicito" ≠ "Requiero". El verbo ES la accion legal. "Exijo" es el mas fuerte. "Solicito" es neutro. Para derechos ARCO, usa "exijo" en las peticiones principales.
12. A CONTRARIO: Lo que la ley NO dice tambien es ley. El art. 28 lista los requisitos de la solicitud — si un requisito no esta en esa lista, NO es exigible. Cada excepcion del art. 25 es taxativa — si el caso de la empresa no encaja en una fraccion especifica, la excepcion NO aplica.
13. A FORTIORI: "Quien puede lo mas, puede lo menos." Si la ley protege datos no sensibles, con mayor razon protege datos biometricos. Si la oposicion prevalece frente a transferencias a terceros, con mayor razon frente a afiliadas.
14. REDUCTIO AD ABSURDUM: Si la posicion de la empresa lleva a una conclusion absurda, la posicion es falsa. "Si cada empresa pudiera exigir su formato, el derecho ARCO seria letra muerta. El legislador no pudo haber querido ese resultado."""


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

PIPELINE = """PIPELINE ARCO — OBLIGATORIO seguir este orden. NO omitas herramientas.

1. Carga arco://case/example para la estructura JSON exacta.
2. Carga arco://law/counter_defenses para el arsenal anti-evasion.
3. process_case(case_json) → pipeline completo.
4. counter_defenses(case_json) → genera la seccion DESESTIMACION DE DEFENSAS PREVISIBLES.
5. audit_draft(draft_text) → errores juridicos. NUNCA omitas.
6. audit_argumentation(draft_text) → vicios logicos. NUNCA omitas.
7. assess_case(case_json) → solidez juridica.
8. deadline_timeline(fecha) → plazos.
9. escalation_basis(etapa="amparo") → fundamento para amparo.

EL BORRADOR NO ESTA LISTO hasta que:
- Incluye DESESTIMACION DE DEFENSAS PREVISIBLES.
- audit_draft devuelva pass=true con 0 findings severity high.
- audit_argumentation devuelva pass=true con 0 findings severity high.

TONO: Se exige con fundamento legal, no se "solicita amablemente". Firme, directo. Sin eufemismos.

Reglas: placeholders → NO redactes. Salud/biometria sin sensible=true → BLOQUEA. Oposicion sin dano concreto → BLOQUEA. >180d sin aviso reconsultado → ADVIERTE. NUNCA cites INAI/IFAI/PRODATOS."""

CASE_EXAMPLE = """ESTRUCTURA DEL JSON DE CASO — usa estos nombres EXACTOS de campo.

{
  \"titular\": {
    \"nombre_completo\": \"NOMBRE COMPLETO\",
    \"identificacion\": {
      \"tipo\": \"INE\",
      \"vigente\": true,
      \"se_adjunta_copia\": true
    }
  },
  \"solicitud\": {
    \"ciudad\": \"Ciudad, Estado\",
    \"fecha\": \"YYYY-MM-DD\"
  },
  \"medio_notificaciones\": {
    \"tipo\": \"correo electronico\",
    \"valor\": \"email@ejemplo.com\"
  },
  \"responsable\": {
    \"naturaleza\": \"privado\",
    \"nombre_legal\": \"RAZON SOCIAL EXACTA S.A. DE C.V.\",
    \"domicilio\": \"Domicilio del aviso de privacidad\",
    \"canal_arco\": \"correo@empresa.com\",
    \"fuente_aviso_privacidad\": {
      \"tipo\": \"URL oficial\",
      \"referencia\": \"https://empresa.com/aviso-privacidad\",
      \"fecha_consulta\": \"YYYY-MM-DD\",
      \"es_fuente_oficial\": true
    }
  },
  \"relacion_juridica\": {
    \"tipo\": \"cliente\",
    \"descripcion\": \"Descripcion de la relacion con la empresa\"
  },
  \"datos_personales\": [
    {
      \"descripcion\": \"Nombre del dato\",
      \"categoria\": \"identificacion\",
      \"sensible\": false
    }
  ],
  \"derechos_solicitados\": [
    {
      \"tipo\": \"acceso\",
      \"peticion_concreta\": \"Conocer los datos personales en posesion del responsable\"
    }
  ],
  \"anexos\": [\"Copia de identificacion oficial vigente\"]
}

IMPORTANTE:
- naturaleza debe ser \"privado\" (NO \"empresa\", NO \"sociedad\", NO \"persona moral\")
- datos_personales es un ARRAY de objetos con \"descripcion\", \"categoria\", \"sensible\"
- sensible es booleano (true/false), NO string \"true\"/\"false\"
- fuente_aviso_privacidad.fecha_consulta en formato ISO YYYY-MM-DD
- fuente_aviso_privacidad.es_fuente_oficial debe ser true (booleano)
- Si ejerces oposicion, agrega: causa_legitima_oposicion, situacion_especifica_oposicion, dano_o_perjuicio_oposicion
"""

STYLE_GUIDE = """GUIA DE REDACCION JURIDICA MEXICANA

Usa esta guia para refinar borradores ARCO despues de audit_draft.

═══ METODO CRAC ═══

Estructura nativa SCJN. Cada peticion en 4 bloques:

  I. CONCLUSION INICIAL (Tesis). Primera linea: que exiges. Sin preambulos.
     Ej: "Exijo la cancelacion de mis datos no requeridos por ley."

  II. REGLA (Fundamento). Cita el articulo exacto.
     Ej: "El articulo 24 de la Ley establece el derecho de cancelacion."

  III. APLICACION (Subsuncion). Conecta la regla con los hechos concretos.
     Ej: "El responsable trata mis datos de geolocalizacion, los cuales no son
     necesarios para proveer el servicio de telefonia contratado."

  IV. CONCLUSION FINAL (Peticion). Cierra reiterando el efecto juridico.
     Ej: "Por tanto, exijo el bloqueo y supresion de dichos datos."

═══ LO DICHO vs LO IMPLICADO ═══

La autoridad SOLO se pronuncia sobre lo EXPLICITO. Lo implicado no vincula.
Cada peticion debe declarar explicitamente: el derecho, el articulo, y la consecuencia.

DEBIL: "Me preocupa el uso de mis datos para mercadotecnia."
FUERTE: "Solicito el cese del tratamiento de mis datos para fines de mercadotecnia,
con fundamento en el articulo 26, fraccion I, de la Ley."

═══ 4 REGLAS DE ORO ═══

1. PARRAFOS DE 5 LINEAS MAXIMO.

2. VOZ ACTIVA (Sujeto → Verbo → Predicado).

3. GERUNDIO SOLO SIMULTANEIDAD. Reemplaza TODO gerundio por "que + verbo" o "y + verbo".

4. ECONOMIA: SUPRIME LO REDUNDANTE.
   Si el lector ya conoce la premisa, no la expliques.
   Cada oracion debe ganar terreno juridico. Si no avanza el argumento, borrala.

5. ENTIMEMA: NO EXPLIQUES LO OBVIO.
   La empresa conoce la ley. No se la expliques. Solo citala.
   "El articulo 28 exige nombre, domicilio y documentos de identidad."
   No digas: "El articulo 28 de la ley, que regula los requisitos de las
   solicitudes ARCO, establece que el titular debe proporcionar..."

═══ VERDAD LITERAL ═══

Solo lo LITERALMENTE dicho obliga. Lo inferido no.
Elige palabras que no puedan torcerse en tu contra.

═══ CARGA DE LA PRUEBA ═══

Quien afirma algo, debe probarlo. NO aceptes la inversion de esta regla.
Si la empresa alega que el tratamiento es "necesario", ELLA debe probarlo.
Si la empresa alega que "consentiste", ELLA debe exhibir el consentimiento.
NUNCA escribas "salvo que no sean necesarios" — escribi "salvo que el
responsable acredite, con evidencia, que son indispensables".

═══ ARGUMENTO NECESARIO (no persuasivo) ═══

Cada peticion debe ser un silogismo cerrado: Norma + Hecho = Conclusion.
Si la conclusion no se sigue NECESARIAMENTE de las premisas, no sirve.
NO: "mis datos podrian usarse indebidamente"
SI:  "art. 26-I otorga oposicion por causa legitima. [Hecho concreto].
      Por tanto, el cese es obligatorio."

═══ ANTES vs DESPUES ═══

ESTILO TRADICIONAL (debil):
"Que por medio del presente ocurso y resultando a todas luces infundado el dicho
del solicitante, toda vez que resulta menester precisar que mi representada se
encuentra impedida para realizar la cancelacion solicitada..."

ESTILO CRAC (fuerte):
I. Improcedencia de la cancelacion por obligacion legal.
Esta empresa no es omisa; la cancelacion es legalmente improcedente.
El articulo 26 de la Ley establece que no procede cancelar cuando el tratamiento
sea necesario para cumplir una obligacion legal.
El solicitante fue cliente de esta institucion financiera. El articulo 115 de la
Ley de Instituciones de Credito obliga a conservar el expediente por 10 anos.
Dado que el plazo de 10 anos no ha transcurrido, esta empresa tiene la obligacion
legal de conservar los datos. Solicito se declare justificada la negativa.

═══ COMO USAR ═══

1. Genera el borrador con process_case.
2. audit_draft → corrige errores juridicos.
3. Aplica esta guia → refina estilo (parrafos, CRAC, voz activa).
4. Vuelve a audit_draft para verificar."""

COUNTER_DEFENSES_ARSENAL = {
    "proposito": "Mapeo de defensas corporativas comunes contra ARCO con sus contra-articulos. Usar para generar contra-defensas especificas en el borrador.",
    "instrucciones_para_llm": (
        "Genera UN PARRAFO POR DEFENSA en DESESTIMACION DE DEFENSAS PREVISIBLES: "
        "(1) nombra la defensa, (2) cita el articulo que la destruye, "
        "(3) explica por que es improcedente."
    ),
    "categorias_defensas_corporativas": [
        {
            "categoria": "Rechazo formal/administrativo",
            "descripcion": "La empresa intenta rechazar la solicitud por razones de forma, no de fondo",
            "tacticas": [
                {
                    "tactica": "Exigir formato corporativo especifico",
                    "contra_articulo": "art. 28 LFPDPPP: la ley define requisitos minimos de contenido, no de formato",
                },
                {
                    "tactica": "Solicitar documentacion adicional en cadena",
                    "contra_articulo": "art. 28-II y art. 32 LFPDPPP: solo se requiere ID; prevencion UNA SOLA VEZ en 5 dias",
                },
                {
                    "tactica": "Alegar ambiguedad u oscuridad",
                    "contra_articulo": "art. 28-IV, V y art. 33 LFPDPPP: prevencion en 5 dias, negativa fundada y motivada",
                },
                {
                    "tactica": "Desconocer el medio de notificacion senalado",
                    "contra_articulo": "art. 30 y 31 LFPDPPP: respuesta por el mismo medio",
                },
                {
                    "tactica": "Rechazar identificacion oficial (INE)",
                    "contra_articulo": "art. 28-II LFPDPPP: solo exige documentos que acrediten identidad",
                },
                {
                    "tactica": "Buzon unico, formularios web con registro obligatorio, rechazo de adjuntos o dominios",
                    "contra_articulo": "art. 30 LFPDPPP: medios electronicos o cualquier otro medio sin restricciones",
                },
            ],
        },
        {
            "categoria": "Negacion jurisdiccional",
            "descripcion": "La empresa alega que la LFPDPPP no le aplica o que los datos no estan protegidos",
            "tacticas": [
                {
                    "tactica": "Negar sujecion a la LFPDPPP",
                    "contra_articulo": "art. 1 y art. 5 LFPDPPP: orden publico, observancia general, particulares",
                },
                {
                    "tactica": "Alegar que la relacion ya concluyo y no hay derecho ARCO",
                    "contra_articulo": "art. 1 y art. 21 LFPDPPP: todo tratamiento, toda persona, sin condicion de vigencia",
                },
            ],
        },
        {
            "categoria": "Falsos cumplimientos",
            "descripcion": "La empresa afirma haber cumplido sin evidencia verificable",
            "tacticas": [
                {
                    "tactica": "Afirmar cumplimiento sin evidencia concreta",
                    "contra_articulo": "art. 22, 23, 24, 25, 26, 31 LFPDPPP: obligacion de hacer efectivo y acreditar",
                },
            ],
        },
        {
            "categoria": "Obstruccion operativa",
            "descripcion": "La empresa culpa a su estructura interna como excusa",
            "tacticas": [
                {
                    "tactica": "Derivar entre departamentos sin resolver",
                    "contra_articulo": "art. 29 LFPDPPP: obligacion de designar responsable de datos personales",
                },
            ],
        },
        {
            "categoria": "Falsos consentimientos y excepciones",
            "descripcion": "La empresa alega consentimiento o excepciones legales inexistentes o mal aplicadas",
            "tacticas": [
                {
                    "tactica": "Invoca excepcion de transferencia a afiliadas (art. 36-III)",
                    "contra_articulo": "art. 26-II y art. 36 parr. 2o LFPDPPP: oposicion expresa prevalece; transferencia debe estar en aviso",
                },
                {
                    "tactica": "Invoca interes legitimo sin base en ley mexicana",
                    "contra_articulo": "art. 7 LFPDPPP: consentimiento expreso; la ley mexicana no contempla interes legitimo autonomo",
                },
                {
                    "tactica": "Alegar necesidad para la relacion juridica (finalidades necesarias)",
                    "contra_articulo": "art. 11, art. 15-IV, art. 35, art. 36 LFPDPPP: distinguir necesario de secundario",
                },
                {
                    "tactica": "Invoca consentimiento tacito por no oposicion o continuidad de uso",
                    "contra_articulo": "art. 7, art. 8 LFPDPPP: consentimiento tacito limitado; no aplica a datos sensibles/patrimoniales; no renuncia derechos ARCO",
                },
            ],
        },
        {
            "categoria": "Excepciones de cancelacion mal aplicadas",
            "descripcion": "La empresa invoca el art. 25 sin especificar fraccion ni justificar",
            "tacticas": [
                {
                    "tactica": "Invoca art. 25 generico para negar cancelacion",
                    "contra_articulo": "art. 25 y art. 3 LFPDPPP: identificar fraccion, dato, finalidad; interpretacion restrictiva de limites",
                },
            ],
        },
        {
            "categoria": "Incumplimiento de aviso de privacidad",
            "descripcion": "La empresa usa deficiencias de su propio aviso como defensa",
            "tacticas": [
                {
                    "tactica": "Aviso ausente, inaccesible o con finalidades ambiguas",
                    "contra_articulo": "art. 15-20 LFPDPPP: requisitos exhaustivos del aviso; su incumplimiento es infraccion adicional, no defensa",
                },
            ],
        },
        {
            "categoria": "Dilacion de plazos",
            "descripcion": "La empresa manipula los plazos legales para desgastar al titular",
            "tacticas": [
                {
                    "tactica": "Dilatar mas alla de 20 dias o ampliar sin justificacion",
                    "contra_articulo": "art. 31 LFPDPPP: 20 dias habiles + UNA ampliacion con justificacion notificada dentro del plazo",
                },
            ],
        },
    ],
}

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
    "counter_defenses": {
        "description": "Arsenal tactico anti-evasion corporativa. Devuelve las tacticas de evasion aplicables al caso con sus contra-articulos exactos y articulos completos. Usala ANTES de redactar la seccion DESESTIMACION DE DEFENSAS PREVISIBLES.",
        "inputSchema": {
            "type": "object",
            "properties": {"case_json": {"type": "string"}},
            "required": ["case_json"],
        },
    },
    "legal_graph": {
        "description": "Grafo de relaciones semanticas entre articulos. Dado uno o mas articulos, devuelve TODAS las relaciones juridicas (requires, limits, overrides, complements). Incluye IDs de articulos para consultar con law_articles.",
        "inputSchema": {
            "type": "object",
            "properties": {"article_numbers_json": {"type": "string", "default": "[]"}},
        },
    },
    "semantic_search": {
        "description": "Busqueda semantica global sobre el grafo juridico. Dada una pregunta en lenguaje natural, encuentra las comunidades mas relevantes y los articulos especificos.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "default": ""}},
        },
    },
    "community_detail": {
        "description": "Detalle completo de una comunidad del grafo juridico con todos los articulos, relaciones internas y conexiones externas.",
        "inputSchema": {
            "type": "object",
            "properties": {"community_id": {"type": "string", "default": ""}},
        },
    },
    "health": {
        "description": "Verifica que el MCP este operativo. Devuelve version, articulos, nodos del grafo y comunidades activas. Usala al inicio de cada sesion.",
        "inputSchema": {
            "type": "object",
            "properties": {},
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
        "counter_defenses": _counter_defenses_call,
        "legal_graph": _legal_graph_call,
        "semantic_search": _semantic_search_call,
        "community_detail": _community_detail_call,
        "health": _health_call,
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


def _counter_defenses_call(case_json: str) -> Any:
    return counter_defenses(require_case_json(case_json, "counter_defenses"))


def _legal_graph_call(article_numbers_json: str = "[]") -> Any:
    import json as _json_std
    try:
        ids = _json_std.loads(article_numbers_json)
        if not isinstance(ids, list):
            ids = []
    except (json.JSONDecodeError, TypeError):
        ids = []
    return legal_graph(ids)


def _semantic_search_call(query: str = "") -> Any:
    return semantic_search(query)


def _community_detail_call(community_id: str = "") -> Any:
    return community_detail(community_id)


def _health_call() -> Any:
    from . import __version__
    from .engine import LEGAL_GRAPH, _COMMUNITIES, CORPORATE_EVASION_TACTICS
    from .law import ARTICLES, REGULATION_ARTICLES
    return {
        "ok": True,
        "version": __version__,
        "status": "healthy",
        "legal_instruments": 5,
        "articles_lfpdppp": len(ARTICLES),
        "articles_regulation": len(REGULATION_ARTICLES),
        "graph_nodes": len(LEGAL_GRAPH),
        "graph_relationships": sum(len(v) for v in LEGAL_GRAPH.values()),
        "communities": len(_COMMUNITIES),
        "counter_defense_tactics": len(CORPORATE_EVASION_TACTICS),
        "message": (
            "El MCP esta operativo. Para empezar: "
            "1. Carga arco://case/example para la estructura JSON. "
            "2. Pregunta al usuario sus datos. "
            "3. Usa validate_case antes de process_case."
        ),
    }


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
        """Audita si un caso ARCO esta listo para redactarse sin huecos legales criticos.                datos personales, derechos solicitados y anexos.
        """
        return _json(_validate_case_call(case_json))

    @mcp.tool()
    def audit_identity(case_json: str) -> str:
        """Detecta riesgos de responsable incorrecto, nombre comercial, sucursal o canal ARCO no oficial.        """
        return _json(_audit_identity_call(case_json))

    @mcp.tool()
    def source_audit(case_json: str) -> str:
        """Audita procedencia, fuente oficial y frescura del aviso de privacidad.        """
        return _json(_source_audit_call(case_json))

    @mcp.tool()
    def select_basis(case_json: str) -> str:
        """Selecciona articulos aplicables sin sobrecitar ni usar articulos fuera de alcance.        """
        return _json(_select_basis_call(case_json))

    @mcp.tool()
    def draft_request(case_json: str) -> str:
        """Redacta una solicitud ARCO solo si el caso supera la validacion critica.        """
        return _json(_draft_request_call(case_json))

    @mcp.tool()
    def argument_map(case_json: str) -> str:
        """Construye mapa de argumentos y limites legales antes de redactar.        """
        return _json(_argument_map_call(case_json))

    @mcp.tool()
    def audit_draft(draft_text: str, case_json: str = "") -> str:
        """Audita un borrador ARCO para detectar autoridad equivocada, articulos mal usados y amenazas sancionatorias imprecisas.        """
        return _json(_audit_draft_call(draft_text, case_json))

    @mcp.tool()
    def deadline_timeline(
        fecha_recepcion: str,
        fecha_respuesta: str = "",
        holidays_json: str = "[]",
        fecha_presentacion_secretaria: str = "",
        fecha_notificacion_secretaria: str = "",
    ) -> str:
        """Calcula plazos ARCO en dias habiles."""
        return _json(_deadline_call(fecha_recepcion, fecha_respuesta, holidays_json, fecha_presentacion_secretaria, fecha_notificacion_secretaria))

    @mcp.tool()
    def law_articles(article_numbers_json: str = "[]") -> str:
        """Devuelve matriz controlada de articulos de la LFPDPPP 2025.        """
        return _json(_law_articles_call(article_numbers_json))

    @mcp.tool()
    def escalation_basis(etapa: str = "escalamiento_secretaria") -> str:
        """Fundamento legal completo para fase de escalamiento: LFPDPPP + LFPA + Ley de Amparo + Constitucion.        """
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

    @mcp.tool()
    def counter_defenses(case_json: str) -> str:
        """Arsenal tactico anti-evasion corporativa. Mapea las tacticas mas comunes
        que las empresas usan para evadir ARCO (formato forzoso, documentacion extra,
        ambiguedad alegada, negacion jurisdiccional, etc.) y devuelve para cada una
        el articulo exacto que la destruye y el argumento juridico contundente.
        Usala ANTES de redactar el borrador para armar la seccion de contra-defensas.
        """
        return _json(_counter_defenses_call(case_json))

    @mcp.tool()
    def legal_graph(article_numbers_json: str = "[]") -> str:
        """Grafo de relaciones semanticas entre articulos de la LFPDPPP, Reglamento,
        LFPA, Ley de Amparo y Constitucion. Dado uno o mas articulos, devuelve TODAS
        las relaciones juridicas: requires (fundamento), limits (restringe), overrides
        (prevalece), complements (detalla), procedural (paso siguiente). Incluye el
        texto completo de cada articulo relacionado. Usala cuando necesites entender
        COMO interactuan los articulos entre si, no solo su contenido aislado.
        """
        return _json(_legal_graph_call(article_numbers_json))

    @mcp.tool()
    def semantic_search(query: str = "") -> str:
        """Busqueda semantica global sobre el grafo juridico. Dada una pregunta en
        lenguaje natural (ej: 'que articulos aplican para oponerme a una transferencia
        de datos'), encuentra las comunidades mas relevantes y los articulos especificos.
        Devuelve los IDs de comunidad para profundizar con community_detail.
        """
        return _json(_semantic_search_call(query))

    @mcp.tool()
    def community_detail(community_id: str = "") -> str:
        """Detalle completo de una comunidad del grafo juridico. Devuelve todos los
        articulos con su texto, relaciones internas entre ellos, y conexiones con otras
        comunidades. Usala despues de semantic_search para profundizar.
        """
        return _json(_community_detail_call(community_id))

    @mcp.tool()
    def health() -> str:
        """Verifica que el MCP esta operativo y devuelve estadisticas del sistema:
        version, numero de articulos cargados, nodos del grafo, comunidades activas.
        Usala al INICIO de cada sesion para confirmar que todo funciona.
        """
        return _json(_health_call())

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
        "arco://case/example",
        name="case_json_example",
        description="Ejemplo completo de la estructura JSON que espera process_case. Carga esto para ver los nombres exactos de campos.",
        mime_type="application/json",
    )
    def resource_case_example() -> str:
        return CASE_EXAMPLE

    @mcp.resource(
        "arco://writing/style",
        name="writing_style_guide",
        description="Guia de redaccion juridica mexicana: metodo CRAC, reglas de oro y ejemplos. Cargala para refinar el estilo de borradores.",
        mime_type="text/plain",
    )
    def resource_style_guide() -> str:
        return STYLE_GUIDE

    @mcp.resource(
        "arco://law/regulation",
        name="regulation_articles",
        description="Principios procesales VIGENTES del Reglamento LFPDPPP 2011. ADVERTENCIA: el reglamento no ha sido armonizado con el decreto 2025. Referencias al INAI/Instituto deben leerse como Secretaria Anticorrupcion. Solo los principios procesales extraidos son validos.",
        mime_type="application/json",
    )
    def resource_regulation_articles() -> str:
        return _json(REGULATION_ARTICLES)

    @mcp.resource(
        "arco://law/counter_defenses",
        name="counter_defenses_arsenal",
        description="Arsenal tactico anti-evasion corporativa. Mapea cada tactica de evasion empresarial al articulo exacto que la destruye. El LLM debe usar esto para generar contra-defensas especificas en el borrador.",
        mime_type="application/json",
    )
    def resource_counter_defenses() -> str:
        return _json(COUNTER_DEFENSES_ARSENAL)

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
            "uri": "arco://case/example",
            "name": "case_json_example",
            "description": "Ejemplo completo de la estructura JSON del caso ARCO con nombres exactos de campos.",
            "mimeType": "application/json",
        },
        {
            "uri": "arco://writing/style",
            "name": "writing_style_guide",
            "description": "Guia de redaccion juridica mexicana: metodo CRAC y reglas de oro.",
            "mimeType": "text/plain",
        },
        {
            "uri": "arco://law/counter_defenses",
            "name": "counter_defenses_arsenal",
            "description": "Arsenal tactico anti-evasion corporativa. Mapea tacticas a articulos que las destruyen.",
            "mimeType": "application/json",
        },
        {
            "uri": "arco://law/regulation",
            "name": "regulation_articles",
            "description": "Articulos clave del Reglamento LFPDPPP con principios procesales vigentes.",
            "mimeType": "application/json",
        },
    ]
    resource_data = {
        "arco://prompt/system": ("text/plain", SYSTEM_PROMPT),
        "arco://law/matrix": ("application/json", _json(article_bundle())),
        "arco://workflow/checklist": ("application/json", _json(CHECKLIST)),
        "arco://research/external-learnings": ("application/json", _json(EXTERNAL_RESEARCH)),
        "arco://workflow/pipeline": ("text/plain", PIPELINE),
        "arco://law/overview": ("text/plain", LEGAL_OVERVIEW),
        "arco://case/example": ("application/json", CASE_EXAMPLE),
        "arco://writing/style": ("text/plain", STYLE_GUIDE),
        "arco://law/counter_defenses": ("application/json", _json(COUNTER_DEFENSES_ARSENAL)),
        "arco://law/regulation": ("application/json", _json(REGULATION_ARTICLES)),
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
