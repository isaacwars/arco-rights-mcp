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


SYSTEM_PROMPT = """ARCO MCP v0.3.0 — Semantic Graph RAG + 5 instrumentos legales.

AUTORIDAD: Secretaria Anticorrupcion y Buen Gobierno (NO INAI).
LEY VIGENTE: LFPDPPP decreto 20-mar-2025. La ley de 2010 fue ABROGADA.

ARQUITECTURA — 3 capas:

  CAPA 1 — BUSQUEDA SEMANTICA (GraphRAG):
    semantic_search("tu pregunta en lenguaje natural")
      → encuentra las comunidades juridicas relevantes
    community_detail("c_transfers")
      → todos los articulos de esa comunidad con texto completo
    legal_graph(["26","36"])
      → como interactuan los articulos: requires, limits, overrides...

  CAPA 2 — CONTENIDO LEGAL:
    law_articles(["28","31","36"])  → texto completo de articulos
    counter_defenses(case_json)     → arsenal anti-evasion corporativa
    escalation_basis(etapa)         → fundamento para Secretaria o Amparo

  CAPA 3 — REDACCION Y AUDITORIA:
    process_case(case_json)  → pipeline completo: valida + redacta + audita
    audit_draft()            → errores juridicos (24 patrones)
    audit_argumentation()    → vicios logicos (14 patrones)
    assess_case()            → solidez juridica
    deadline_timeline()      → plazos en dias habiles

FLUJO OBLIGATORIO:
  1. semantic_search(pregunta) para orientarte
  2. process_case(case_json) para pipeline completo
  3. counter_defenses(case_json) para seccion DESESTIMACION DE DEFENSAS
  4. audit_draft → 0 findings high = listo
  5. audit_argumentation → NUNCA omitas
  6. assess_case → nivel "solido" o superior
  7. deadline_timeline → plazos exactos

CARGA AL INICIO: arco://workflow/pipeline, arco://law/counter_defenses, arco://case/example

REGLAS: Cada peticion cita su articulo exacto. El derecho ARCO se EXIGE, no se pide. Si must_use_tools aparece, EJECUTALO. NUNCA cites INAI. Empresa no puede exigir formato propio (art. 28). Plazo 20 dias HABILES (art. 31). Oposicion expres PREVALECE sobre transferencia afiliadas (art. 26 vs 36-III)."""


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

1. Carga arco://case/example para ver la estructura JSON exacta.
2. Carga arco://law/counter_defenses para conocer el arsenal anti-evasion.
3. process_case(case_json) → pipeline completo en una llamada.
4. counter_defenses(case_json) → identifica las defensas que la empresa podria usar y sus contra-articulos. USA ESTA INFORMACION para redactar la seccion 'DESESTIMACION DE DEFENSAS PREVISIBLES' del borrador.
5. audit_draft(draft_text) → detecta errores jurídicos.
6. audit_argumentation(draft_text) → detecta vicios lógicos. NUNCA omitas este paso.
7. assess_case(case_json) → valora solidez jurídica. Siempre despues de los audits.
8. deadline_timeline(fecha_recepcion) → calcula plazos. Agrega fecha_notificacion_secretaria si aplica.
9. escalation_basis(etapa="amparo") → fundamento completo para amparo.

EL BORRADOR NO ESTA LISTO hasta que:
- Incluye la seccion 'DESESTIMACION DE DEFENSAS PREVISIBLES' con contra-argumentos especificos
- audit_draft devuelva pass=true con 0 findings de severity high
- audit_argumentation devuelva pass=true con 0 findings de severity high
- assess_case devuelva nivel "solido" o superior

Si falta aunque sea UNO de estos pasos, NO entregues el borrador. Vuelve a iterar.

TONO: El derecho ARCO es un derecho constitucional (art. 16 CPEUM). No se "solicita amablemente" — se exige con fundamento legal. La ley esta del lado del titular. Cada peticion debe ser firme, directa y respaldada por el articulo exacto. Sin eufemismos. Sin "por favor". Sin "si no es mucha molestia". Esto es la exigencia de un derecho, no una carta de solicitud de empleo.

CONTRADEFENSAS: CADA empresa tiene su propia marana de avisos de privacidad. La herramienta counter_defenses devuelve las tacticas de evasion mas probables y sus contra-articulos. DEBES generar UN PARRAFO POR DEFENSA en la seccion DESESTIMACION DE DEFENSAS PREVISIBLES. Cada parrafo: (1) nombra la defensa, (2) cita el articulo exacto que la destruye, (3) explica por que es improcedente. Se especifico y quirurgico. El objetivo es que el abogado de la empresa sepa que NO TIENE ESCAPATORIA.

Reglas: si hay placeholders, NO redactes. Si salud/biometria sin sensible=true, BLOQUEA.
Si oposicion sin dano concreto, BLOQUEA. Si >180d sin aviso reconsultado, ADVIERTE.
Nunca cites INAI/IFAI/PRODATOS. Usa Secretaria Anticorrupcion y Buen Gobierno."""

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

COUNTER_DEFENSES_ARSENAL = {
    "proposito": "Arsenal tactico para destruir las defensas corporativas mas comunes que las empresas usan para evadir ARCO. El LLM debe usar esta informacion para generar contra-defensas ESPECIFICAS y QUIRURGICAS en el borrador, adaptadas a la empresa concreta del caso.",
    "instrucciones_para_llm": (
        "CADA empresa tiene su propia marana de aviso de privacidad y tacticas de evasion. "
        "Usa la herramienta counter_defenses para obtener la lista de defensas aplicables al caso concreto. "
        "LUEGO, en la seccion 'DESESTIMACION DE DEFENSAS PREVISIBLES' del borrador, "
        "genera UN PARRAFO POR CADA DEFENSA que: (1) nombre la defensa que la empresa podria intentar, "
        "(2) cite el articulo EXACTO que la destruye, y (3) explique por que es juridicamente improcedente. "
        "NO uses lenguaje generico. Se especifico, quirurgico, contundente. "
        "El objetivo es que cuando el abogado de la empresa lea el borrador, SEPA QUE NO TIENE ESCAPATORIA LEGAL. "
        "Cada parrafo debe cerrar con la consecuencia juridica de intentar esa defensa (infraccion, sancion, negativa infundada)."
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
        description="Articulos clave del Reglamento LFPDPPP 2011 con principios procesales VIGENTES contra evasion corporativa. Advertencia: referencias al INAI/Instituto deben leerse como Secretaria Anticorrupcion.",
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
