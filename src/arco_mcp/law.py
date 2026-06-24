"""Normative matrix for the LFPDPPP issued in the 2025 decree.

The entries are intentionally concise. They are not a replacement for the
official legal text; they are a controlled map that prevents the drafting
engine from citing articles outside their scope.
"""

DECREE_SOURCE = (
    "Decreto publicado el 20 de marzo de 2025 que expide la Ley Federal de "
    "Proteccion de Datos Personales en Posesion de los Particulares."
)

AUTHORITY = "Secretaria Anticorrupcion y Buen Gobierno"


ARTICLES = {
    "1": {
        "title": "Objeto de la Ley",
        "use": "Marco general de privacidad y autodeterminacion informativa.",
    },
    "2": {
        "title": "Definiciones",
        "use": "Define aviso de privacidad, responsable, Secretaria, titular, tratamiento, transferencia y dias habiles.",
    },
    "3": {
        "title": "Limites generales",
        "use": "Los principios y derechos tienen como limite seguridad nacional, orden, seguridad y salud publicos, y derechos de terceros.",
    },
    "4": {
        "title": "Supletoriedad",
        "use": "A falta de disposicion expresa aplican supletoriamente el Codigo Federal de Procedimientos Civiles y la Ley Federal de Procedimiento Administrativo.",
    },
    "5": {
        "title": "Principios",
        "use": "Licitud, finalidad, lealtad, consentimiento, calidad, proporcionalidad, informacion y responsabilidad.",
    },
    "6": {
        "title": "Licitud y medios no enganosos",
        "use": "Util cuando el caso involucra recoleccion enganosa o fraudulenta.",
    },
    "7": {
        "title": "Consentimiento y revocacion",
        "use": "Usar si se revoca consentimiento o el tratamiento depende de consentimiento.",
    },
    "8": {
        "title": "Datos sensibles",
        "use": "Consentimiento expreso y por escrito; bases sensibles solo con finalidad legitima, concreta y acorde.",
    },
    "9": {
        "title": "Excepciones al consentimiento",
        "use": "Permite anticipar defensas del responsable cuando existe ley, contrato, emergencia u orden de autoridad.",
    },
    "10": {
        "title": "Calidad y supresion",
        "use": "Datos exactos, completos, correctos y actualizados; supresion cuando dejan de ser necesarios, previo bloqueo.",
    },
    "11": {
        "title": "Finalidad",
        "use": "Tratamiento limitado al aviso de privacidad; finalidades distintas requieren nuevo consentimiento.",
    },
    "12": {
        "title": "Proporcionalidad",
        "use": "Tratamiento necesario, adecuado y relevante; util para datos excesivos.",
    },
    "13": {
        "title": "Responsabilidad",
        "use": "El responsable debe aplicar principios y respetar el aviso, incluso respecto de terceros relacionados.",
    },
    "14": {
        "title": "Informacion por aviso",
        "use": "Obligacion de informar al titular mediante aviso de privacidad.",
    },
    "15": {
        "title": "Contenido minimo del aviso",
        "use": "Identidad y domicilio del responsable; datos tratados; finalidades; limitacion de uso/divulgacion; mecanismos ARCO.",
    },
    "16": {
        "title": "Puesta a disposicion del aviso",
        "use": "El responsable debe poner el aviso a disposicion por medios impresos, digitales, visuales, sonoros u otra tecnologia, segun forma de obtencion.",
    },
    "17": {
        "title": "Aviso cuando datos no se recaban directamente",
        "use": "Cuando los datos no se obtengan directamente del titular, el responsable debe darle a conocer el cambio en el aviso. No aplica para fines historicos, estadisticos o cientificos. Si es imposible o exige esfuerzos desproporcionados, pueden adoptarse medidas compensatorias segun el Reglamento.",
    },
    "18": {
        "title": "Medidas de seguridad",
        "use": "Seguridad administrativa, tecnica y fisica.",
    },
    "19": {
        "title": "Vulneraciones de seguridad",
        "use": "Vulneraciones que afecten significativamente derechos patrimoniales o morales deben informarse de inmediato al titular.",
    },
    "20": {
        "title": "Confidencialidad",
        "use": "Deber de confidencialidad para quienes intervienen en el tratamiento.",
    },
    "21": {
        "title": "Habilitacion ARCO",
        "use": "Cualquier titular o representante puede ejercer derechos ARCO; un derecho no exige ni impide otro.",
    },
    "22": {
        "title": "Acceso",
        "use": "Acceso a datos en posesion del responsable y condiciones generales del tratamiento.",
    },
    "23": {
        "title": "Rectificacion",
        "use": "Correccion de datos inexactos, incompletos o no actualizados.",
    },
    "24": {
        "title": "Cancelacion",
        "use": "Cancelacion, bloqueo previo, supresion posterior y aviso al titular; comunicacion a terceros cuando aplique.",
    },
    "25": {
        "title": "Excepciones de cancelacion",
        "use": "Contrato, disposicion legal, actuaciones judiciales/administrativas, intereses juridicos, interes publico, obligacion legal o salud.",
    },
    "26": {
        "title": "Oposicion",
        "use": "Procede por causa legitima y situacion especifica, o por tratamiento automatizado con efectos juridicos no deseados o afectacion significativa; no procede si el tratamiento es necesario por obligacion legal.",
    },
    "27": {
        "title": "Solicitud al responsable",
        "use": "El titular o representante puede solicitar ARCO ante el responsable en cualquier momento.",
    },
    "28": {
        "title": "Requisitos de solicitud ARCO",
        "use": "Nombre, domicilio/medio de notificacion, identidad/representacion, datos, derecho o peticion, elementos de localizacion.",
    },
    "29": {
        "title": "Departamento de datos personales",
        "use": "El responsable debe designar persona o departamento para tramitar solicitudes.",
    },
    "30": {
        "title": "Rectificacion: requisitos adicionales",
        "use": "Indicar modificaciones y aportar documentacion soporte.",
    },
    "31": {
        "title": "Plazos ante responsable",
        "use": "Respuesta en 20 dias habiles; efectividad en 15 dias habiles; ampliacion unica por periodo igual con justificacion.",
    },
    "32": {
        "title": "Cumplimiento del acceso",
        "use": "Puesta a disposicion, copias simples, documentos electronicos u otro medio del aviso.",
    },
    "33": {
        "title": "Negativa y prueba",
        "use": "Causas de improcedencia; negativa parcial; debe informar motivo y acompanar pruebas pertinentes.",
    },
    "34": {
        "title": "Gratuidad",
        "use": "ARCO gratuito salvo costos de reproduccion, copias o envio.",
    },
    "35": {
        "title": "Transferencias",
        "use": "Comunicar aviso y finalidades a terceros; clausula de aceptacion o rechazo de transferencias.",
    },
    "36": {
        "title": "Transferencias sin consentimiento",
        "use": "Supuestos permitidos: ley, salud, grupo, contrato, interes publico, defensa judicial o relacion juridica.",
    },
    "37": {
        "title": "Esquemas de autorregulacion vinculante",
        "use": "Personas fisicas o morales pueden convenir esquemas de autorregulacion vinculante que complementen la Ley. Deben contener mecanismos para medir su eficacia, consecuencias y medidas correctivas eficaces. Pueden traducirse en codigos deontologicos, sellos de confianza u otros mecanismos con reglas que armonicen tratamientos y faciliten derechos ARCO. Deben notificarse simultaneamente a las autoridades correspondientes y a la Secretaria. IMPORTANTE: un esquema de autorregulacion NO exime del cumplimiento de la Ley ni puede restringir derechos ARCO.",
    },
    "38": {
        "title": "Objeto de la Secretaria",
        "use": "Promover ejercicio y vigilar observancia de la Ley.",
    },
    "39": {
        "title": "Atribuciones de la Secretaria",
        "use": "Vigilar, verificar, interpretar, resolver proteccion de derechos y sancionar.",
    },
    "40": {
        "title": "Solicitud de proteccion de datos",
        "use": "Procede ante respuesta, falta de respuesta, entrega incompleta, formato incomprensible o negativa.",
    },
    "41": {
        "title": "Requisitos ante Secretaria",
        "use": "Datos del titular, responsable, domicilio, fecha de respuesta, actos y anexos.",
    },
    "42": {
        "title": "Plazo de resolucion de Secretaria",
        "use": "50 dias, ampliable una vez por periodo igual.",
    },
    "43": {
        "title": "Cumplimiento por resolucion favorable",
        "use": "Responsable debe hacer efectivo el derecho en 10 dias o plazo fijado.",
    },
    "44": {
        "title": "Prevencion ante Secretaria",
        "use": "Si faltan requisitos en la solicitud de proteccion, la Secretaria previene una sola vez para subsanar en cinco dias.",
    },
    "45": {
        "title": "Suplencia de deficiencias",
        "use": "La Secretaria puede suplir deficiencias sin alterar solicitud original, hechos ni peticiones.",
    },
    "46": {
        "title": "Tipos de resolucion",
        "use": "La Secretaria puede sobreseer/desechar, confirmar/revocar/modificar respuesta u ordenar entrega de datos.",
    },
    "47": {
        "title": "Improcedencia ante Secretaria",
        "use": "Incluye falta de competencia, identidad/representacion, cosa decidida, juicio en tramite, solicitud ofensiva o extemporanea.",
    },
    "48": {
        "title": "Sobreseimiento de la solicitud de proteccion",
        "use": "La solicitud de proteccion de datos sera sobreseida cuando: I. La persona titular fallezca. El sobreseimiento NO implica validacion del actuar del responsable, solo la terminacion del procedimiento por causa superveniente.",
    },
    "49": {
        "title": "Conciliacion",
        "use": "La Secretaria puede buscar conciliacion; acuerdo escrito tiene efectos vinculantes y deja sin materia la solicitud.",
    },
    "50": {
        "title": "Falta de respuesta",
        "use": "Secretaria da vista al responsable para acreditar respuesta o responder.",
    },
    "51": {
        "title": "Amparo",
        "use": "Contra resoluciones de la Secretaria procede juicio de amparo.",
    },
    "52": {
        "title": "Publicidad de resoluciones",
        "use": "Todas las resoluciones de la Secretaria seran susceptibles de difundirse publicamente en versiones publicas, eliminando referencias que identifiquen o hagan identificable al titular.",
    },
    "53": {
        "title": "Indemnizacion",
        "use": "El titular puede ejercer derechos para indemnizacion por dano o lesion causado por incumplimiento del responsable o encargado.",
    },
    "54": {
        "title": "Verificacion",
        "use": "Verificacion de oficio o a peticion de parte.",
    },
    "55": {
        "title": "Acceso a informacion en verificacion",
        "use": "En el procedimiento de verificacion la Secretaria tendra acceso a la informacion y documentacion que considere necesarias. Las personas servidoras publicas estan obligadas a guardar confidencialidad sobre la informacion conocida en la verificacion. El Reglamento desarrollara la forma, terminos y plazos del procedimiento.",
    },
    "56": {
        "title": "Inicio de sanciones",
        "use": "Si en proteccion o verificacion hay presunto incumplimiento, inicia procedimiento sancionador.",
    },
    "57": {
        "title": "Procedimiento sancionador",
        "use": "Notificacion de hechos, quince dias para pruebas, alegatos y resolucion en cincuenta dias, ampliable una vez.",
    },
    "58": {
        "title": "Infracciones",
        "use": "Lista infracciones: incumplimiento ARCO, negligencia, dolo, principios, aviso, transferencias, verificacion, uso ilegitimo, etc.",
    },
    "59": {
        "title": "Sanciones",
        "use": "Apercibimiento o multas segun fraccion infringida; no hay multa automatica para toda solicitud.",
    },
    "60": {
        "title": "Graduacion",
        "use": "Naturaleza del dato, improcedencia notoria, intencionalidad, capacidad economica y reincidencia.",
    },
    "61": {
        "title": "Responsabilidad civil o penal",
        "use": "Las sanciones administrativas se imponen sin perjuicio de responsabilidad civil o penal.",
    },
    "62": {
        "title": "Delito por vulneracion de seguridad con lucro",
        "use": "Prision por provocar vulneracion de seguridad con animo de lucro estando autorizado para tratar datos.",
    },
    "63": {
        "title": "Delito por tratamiento enganoso con lucro",
        "use": "Prision por tratar datos mediante engano para lucro indebido, aprovechando error del titular o persona autorizada.",
    },
    "64": {
        "title": "Datos sensibles en delitos",
        "use": "Las penas por delitos del capitulo se duplican cuando se trate de datos personales sensibles.",
    },
}


RIGHTS = {
    "acceso": {
        "articles": ["21", "22", "28", "31", "32", "34"],
        "requires_data_description": False,
        "critical_fields": [],
    },
    "rectificacion": {
        "articles": ["21", "23", "28", "30", "31", "34"],
        "requires_data_description": True,
        "critical_fields": [
            "dato_actual_rectificacion",
            "dato_correcto_rectificacion",
            "documento_soporte_rectificacion",
        ],
    },
    "cancelacion": {
        "articles": ["21", "24", "25", "28", "31", "34"],
        "requires_data_description": True,
        "critical_fields": [],
    },
    "oposicion": {
        "articles": ["21", "26", "28", "31", "34"],
        "requires_data_description": True,
        "critical_fields": [
            "causa_legitima_oposicion",
            "situacion_especifica_oposicion",
            "dano_o_perjuicio_oposicion",
        ],
    },
    "limitacion_uso_divulgacion": {
        "articles": ["11", "15", "35", "36"],
        "requires_data_description": True,
        "critical_fields": ["finalidad_objetada"],
        "not_arco": True,
    },
    "revocacion_consentimiento": {
        "articles": ["7", "11", "15", "35", "36"],
        "requires_data_description": True,
        "critical_fields": [],
        "not_arco": True,
    },
}


BASE_ARTICLES = ["21", "27", "28", "29", "31", "33", "34"]
GENERAL_LIMIT_ARTICLES = ["3", "4"]
GENERAL_PROVISIONS = ["1", "2", "5", "6", "9", "10", "13", "14", "16", "17"]
SELF_REGULATION_ARTICLES = ["37"]
SECRETARIA_ARTICLES = ["38", "39", "40", "41", "42", "43", "44", "45", "46", "47", "48", "49", "50", "51", "52", "53", "54", "55"]
SANCTION_ARTICLES = ["56", "57", "58", "59", "60", "61"]
PENAL_ARTICLES = ["62", "63", "64"]
SENSITIVE_ARTICLES = ["8", "12", "18", "19", "20"]
TRANSFER_ARTICLES = ["11", "15", "35", "36"]

# ── Reglamento LFPDPPP 2011 — principios procesales vigentes ──
# El reglamento es de 21-dic-2011 y no ha sido armonizado con el decreto 2025.
# Las referencias a "el Instituto" deben entenderse como la autoridad actual (Secretaria).
# Las referencias a articulos de la "Ley" corresponden a la LFPDPPP 2010; los principios
# juridicos subsisten aunque los numeros de articulo hayan cambiado.
REGULATION_ARTICLES: dict[str, dict[str, str]] = {
    "R44": {
        "title": "Principio de lealtad — prohibicion de medios enganosos o fraudulentos",
        "use": "No se podran utilizar medios enganosos o fraudulentos para recabar y tratar datos personales. Existe actuacion fraudulenta o enganosa cuando: I. Exista dolo, mala fe o negligencia en la informacion proporcionada al titular sobre el tratamiento; II. Se vulnere la expectativa razonable de privacidad del titular; III. Las finalidades no son las informadas en el aviso de privacidad. FUNDAMENTAL: si la empresa oculto finalidades en el aviso, hay dolo.",
    },
    "R68": {
        "title": "Consentimiento para transferencias — aviso obligatorio",
        "use": "Toda transferencia de datos personales, nacional o internacional, requiere consentimiento del titular salvo excepciones de ley, debe ser informada mediante el aviso de privacidad y limitarse a la finalidad que la justifique. Si la transferencia no esta en el aviso, es ilegal.",
    },
    "R69": {
        "title": "Carga de la prueba en transferencias — recae en el responsable",
        "use": "La carga de la prueba de que la transferencia se realizo conforme a la Ley y el Reglamento recae, en TODOS los casos, en el responsable que transfiere y en el receptor de los datos. La empresa no puede exigir al titular que demuestre que la transferencia fue indebida; es la empresa quien debe demostrar que fue licita.",
    },
    "R70": {
        "title": "Transferencias intragrupo — normas internas vinculantes",
        "use": "Las transferencias entre sociedades controladoras, subsidiarias o afiliadas bajo control comun pueden realizarse si existen normas internas de proteccion de datos cuya observancia sea VINCULANTE y cumplan con la Ley y el Reglamento. La mera pertenencia al mismo grupo corporativo NO justifica la transferencia automatica; debe existir normativa interna exigible.",
    },
    "R74": {
        "title": "Transferencias internacionales — mismas obligaciones que el transferente",
        "use": "Las transferencias internacionales solo son posibles cuando el receptor asume las MISMAS obligaciones que corresponden al responsable que transfirio. No basta con que el pais receptor tenga 'nivel adecuado'; el receptor concreto debe comprometerse contractualmente al mismo nivel de proteccion.",
    },
    "R87": {
        "title": "Independencia de derechos ARCO",
        "use": "El ejercicio de cualquiera de los derechos ARCO no excluye la posibilidad de ejercer algun otro, ni la posibilidad de ejercer un derecho constituye requisito para el ejercicio de otro. La empresa no puede condicionar la oposicion a que primero se ejerza el acceso, ni viceversa.",
    },
    "R91": {
        "title": "Canales de atencion al cliente como canal ARCO valido",
        "use": "Cuando el responsable disponga de servicios de atencion al publico o reclamaciones, podra atender las solicitudes ARCO a traves de dichos servicios, siempre que los plazos no contravengan los legales. La identidad del titular se considerara acreditada por los medios establecidos por el responsable para la identificacion en la prestacion de sus servicios. ESTO DESTRUYE EL ARGUMENTO DE 'USE NUESTRO FORMATO ESPECIFICO': los canales existentes de atencion al cliente son juridicamente validos para recibir solicitudes ARCO.",
    },
    "R86": {
        "title": "Registro obligatorio de esquemas de autorregulacion",
        "use": "Los esquemas de autorregulacion notificados forman parte de un registro administrado por la autoridad. Solo los esquemas que cumplan con los parametros legales y esten REGISTRADOS tienen efectos juridicos. Si una empresa alega tener un esquema de autorregulacion pero no esta registrado o no cumple los parametros, NO tiene valor juridico para limitar derechos ARCO.",
    },
}


VALID_RIGHTS = set(RIGHTS)


SOURCE_PROVENANCE_RULES = {
    "primary_case_source": {
        "rule": "La identidad del responsable, domicilio y canal ARCO deben venir del aviso de privacidad vigente del responsable.",
        "legal_risk": "Una fuente de terceros puede contener nombre comercial, razon social anterior, canal no oficial o autoridad obsoleta.",
    },
    "freshness": {
        "rule": "La fecha de consulta del aviso debe estar documentada; si supera 180 dias, se debe reconsultar antes de redactar.",
        "legal_risk": "Los avisos de privacidad pueden cambiar por reformas, reorganizaciones societarias o nuevos canales internos.",
    },
    "third_party_sources": {
        "rule": "GitHub, blogs, notas periodisticas, Wikipedia y compendios privados solo sirven como contexto tecnico o comparativo.",
        "legal_risk": "No sustituyen el DOF ni el aviso de privacidad del responsable en un escrito dirigido a una empresa.",
    },
    "versioned_norms": {
        "rule": "Toda cita normativa debe estar asociada al decreto fuente, articulo exacto y alcance concreto.",
        "legal_risk": "Las fuentes recientes aun mezclan INAI, IFAI-PRODATOS o articulado anterior con el regimen vigente.",
    },
}


EXTERNAL_LEGAL_TECH_LEARNINGS = [
    {
        "source": "Volpsmx/api / Ordina-engine",
        "url": "https://github.com/Volpsmx/api",
        "learning": "Separar resolver norma, buscar articulo, obtener detalle y extraer citas; nunca saltar directo de una pregunta a una cita.",
        "integrated_as": "El MCP mantiene select_basis, law_articles y argument_map como pasos separados.",
    },
    {
        "source": "ingteranalvarez/lex-mx",
        "url": "https://github.com/ingteranalvarez/lex-mx",
        "learning": "Los asistentes legales deben leer texto versionado y fechado, no responder de memoria.",
        "integrated_as": "El MCP exige fuente del decreto y fecha/fuente del aviso de privacidad antes de redactar.",
    },
    {
        "source": "JoshuaPozos/leyes-mexicanas-markdown",
        "url": "https://github.com/JoshuaPozos/leyes-mexicanas-markdown",
        "learning": "Un AST o estructura canonica por articulo reduce errores de chunking, referencias cruzadas y citas fuera de alcance.",
        "integrated_as": "La matriz ARTICLES conserva articulo, titulo y uso autorizado por separado.",
    },
    {
        "source": "Ansvar-Systems/mexican-law-mcp",
        "url": "https://github.com/Ansvar-Systems/mexican-law-mcp",
        "learning": "Un MCP juridico debe exponer busqueda de texto, procedencia, frescura y controles de deriva normativa.",
        "integrated_as": "Se agrega auditoria de procedencia/frescura de fuentes del caso.",
    },
    {
        "source": "soymou/mexican-law-mcp-server",
        "url": "https://github.com/soymou/mexican-law-mcp-server",
        "learning": "Los generadores legales amplios deben declarar limites de actualizacion; para ARCO conviene bloquear antes de inventar.",
        "integrated_as": "draft_request no fuerza redaccion final cuando falta dato critico.",
    },
]


RECENT_ARCO_REFERENCE_NOTES = [
    {
        "source": "Commoner Law - Derechos ARCO en Mexico 2026",
        "url": "https://commoner-law.com/mexico/privacidad-y-derechos-digitales/derechos-arco",
        "note": "Referencia reciente que ya distingue Secretaria Anticorrupcion y Buen Gobierno frente a contenido viejo que cita INAI.",
        "use": "Comparativo de autoridad; no fuente normativa primaria.",
    },
    {
        "source": "SDV Asesores - Articulo 22 LFPDPPP 2026",
        "url": "https://sdv.com.mx/compendio/ley-proteccion-datos-personales/articulo-22/",
        "note": "Aunque se presenta como verificado en 2026, conserva referencias al INAI en el analisis practico.",
        "use": "Ejemplo de por que el MCP debe detectar autoridad obsoleta aun en paginas recientes.",
    },
    {
        "source": "El Pais Mexico - registro de lineas celulares 2026",
        "url": "https://elpais.com/mexico/2026-01-17/los-errores-y-la-fuga-de-datos-personales-manchan-el-primer-intento-masivo-de-registrar-los-celulares-mexicanos.html",
        "note": "Caso reciente de telecomunicaciones con disputa publica sobre CURP, seguridad y posible biometria/prueba de vida.",
        "use": "Contexto factico; el escrito debe basarse en datos realmente recabados y aviso de privacidad del operador.",
    },
]
