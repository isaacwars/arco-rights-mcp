"""Controlled normative matrix for ARCO escalation phase.

Sources:
  - LFPA: Ley Federal de Procedimiento Administrativo (DOF 04-08-1994,
    ultima reforma DOF 14-11-2025). Texto vigente descargado de
    diputados.gob.mx/LeyesBiblio/doc/LFPA.doc
  - Ley de Amparo: DOF 02-04-2013, reglamentaria de los articulos
    103 y 107 constitucionales. Texto extraido del DOF HTML local
    proporcionado por el usuario.
  - Constitucion: CPEUM (DOF 05-02-1917, ultima reforma DOF 02-06-2026).
    Texto vigente descargado de diputados.gob.mx/LeyesBiblio/doc/CPEUM.doc

Each entry is an intentionally concise summary; it is not a replacement
for the official text. The "use" field is strictly derived from the
extracted source text and is verified against it.
"""

# ── LFPA ──────────────────────────────────────────────────────────────
LFPA_SOURCE = (
    "Ley Federal de Procedimiento Administrativo, DOF 04-08-1994, "
    "ultima reforma DOF 14-11-2025."
)

LFPA_ARTICLES: dict[str, dict[str, str]] = {
    "1": {
        "title": "Ambito de aplicacion y orden publico",
        "use": (
            "La LFPA es de orden e interes publicos; aplica a actos, "
            "procedimientos y resoluciones de la APF centralizada y "
            "de organismos descentralizados en sus actos de autoridad. "
            "La Secretaria Anticorrupcion y Buen Gobierno es autoridad "
            "federal administrativa; sus actos estan sujetos a la LFPA "
            "en lo que la LFPDPPP no regule expresamente."
        ),
    },
    "2": {
        "title": "Supletoriedad de la LFPA",
        "use": (
            "La LFPA se aplica supletoriamente a las diversas leyes "
            "administrativas. Como la LFPDPPP es ley administrativa "
            "federal que guarda silencio sobre notificaciones, computo "
            "supletorio de plazos y requisitos formales del acto, la "
            "LFPA cubre esas lagunas por supletoriedad expresa del "
            "articulo 4 de la LFPDPPP."
        ),
    },
    "3": {
        "title": "Elementos y requisitos del acto administrativo",
        "use": (
            "Todo acto administrativo debe: ser expedido por organo "
            "competente (I), tener objeto determinado (II), cumplir "
            "finalidad de interes publico (III), constar por escrito "
            "con firma autografa (IV), estar fundado y motivado (V), "
            "sujetarse al procedimiento (VII), no tener error sobre "
            "objeto/causa/motivo/fin (VIII), no mediar dolo o violencia "
            "(IX). Si la resolucion de la Secretaria omite alguno de "
            "estos requisitos, es nula conforme al articulo 6 de la LFPA."
        ),
    },
    "28": {
        "title": "Computo de plazos en dias habiles",
        "use": (
            "Las actuaciones se practican en dias y horas habiles. En "
            "plazos fijados en dias no se cuentan los inhabiles salvo "
            "disposicion en contrario. Son inhabiles: sabados, domingos, "
            "1o enero, 5 febrero, 21 marzo, 1o mayo, 5 mayo, 1o y 16 "
            "septiembre, 20 noviembre, 1o diciembre (cada 6 anos) y "
            "25 diciembre, mas los dias en que tengan vacaciones "
            "generales las autoridades. Esto suple cualquier ambiguedad "
            "sobre el computo de plazos no detallado en la LFPDPPP."
        ),
    },
    "31": {
        "title": "Ampliacion de plazos por la autoridad",
        "use": (
            "La autoridad puede ampliar terminos y plazos de oficio o "
            "a peticion de parte, sin que la ampliacion exceda en "
            "ningun caso la mitad del plazo original. Esto establece "
            "un tope general: si la LFPDPPP permite ampliacion por "
            "periodo igual, la LFPA confirma que jamas puede superar "
            "la mitad del original; en caso de conflicto aparente "
            "prevalece la regla especial de la LFPDPPP."
        ),
    },
    "35": {
        "title": "Formas de notificacion",
        "use": (
            "Las notificaciones y resoluciones administrativas pueden "
            "realizarse: I. Personalmente en domicilio del interesado; "
            "II. Por oficio con mensajero o correo certificado con "
            "acuse de recibo, o por medios electronicos si el "
            "promovente los acepto y puede comprobarse fehacientemente "
            "la recepcion; III. Por edicto cuando se desconozca el "
            "domicilio. Si la Secretaria notifica por un medio no "
            "previsto o sin acuse, la notificacion es irregular "
            "(art. 40 LFPA)."
        ),
    },
    "38": {
        "title": "Efectos de la notificacion",
        "use": (
            "Las notificaciones personales surten efectos el dia en que "
            "se realizan. Los plazos empiezan a correr a partir del dia "
            "siguiente a aquel en que haya surtido efectos la "
            "notificacion. En correo certificado, la fecha del acuse "
            "es la fecha de notificacion. Esto determina el inicio del "
            "plazo de 15 dias para promover amparo."
        ),
    },
    "39": {
        "title": "Contenido y plazo de la notificacion",
        "use": (
            "Toda notificacion debe efectuarse en maximo 10 dias desde "
            "la emision de la resolucion y debe contener: texto integro "
            "del acto, fundamento legal, indicacion de si es o no "
            "definitivo en via administrativa, y en su caso el recurso "
            "que proceda, organo ante el cual presentarlo y plazo. "
            "Si la Secretaria omite estos requisitos, la notificacion "
            "es defectuosa y afecta el computo del plazo de amparo."
        ),
    },
    "41": {
        "title": "Impugnacion de actos no notificados o mal notificados",
        "use": (
            "Si el acto no fue notificado o la notificacion no se apego "
            "a la LFPA, el afectado puede impugnarlo: si afirma conocer "
            "el acto, manifiesta la fecha en que lo conocio en el "
            "recurso; si niega conocerlo, interpone recurso ante la "
            "autoridad competente para notificar. Esto permite al "
            "titular argumentar que el plazo de amparo no ha empezado "
            "a correr si la notificacion de la Secretaria fue "
            "defectuosa o inexistente."
        ),
    },
}


# ── Ley de Amparo ─────────────────────────────────────────────────────
AMPARO_SOURCE = (
    "Ley de Amparo, Reglamentaria de los articulos 103 y 107 de la "
    "Constitucion Politica de los Estados Unidos Mexicanos, "
    "DOF 02-04-2013."
)

AMPARO_ARTICLES: dict[str, dict[str, str]] = {
    "17": {
        "title": "Plazo para presentar demanda de amparo",
        "use": (
            "El plazo para presentar la demanda de amparo es de quince "
            "dias. Las excepciones (treinta dias para normas "
            "autoaplicativas, ocho anos para sentencia penal "
            "condenatoria, siete anos para privacion de derechos "
            "agrarios) no aplican a la resolucion de la Secretaria "
            "dictada en un procedimiento de proteccion de datos. "
            "El plazo de 15 dias es el aplicable para impugnar la "
            "resolucion de la Secretaria via amparo indirecto."
        ),
    },
    "19": {
        "title": "Dias habiles para el juicio de amparo",
        "use": (
            "Son dias habiles para la promocion, substanciacion y "
            "resolucion de los juicios de amparo todos los del ano, "
            "con excepcion de los sabados y domingos, 1o de enero, "
            "5 de febrero, 21 de marzo, 1o y 5 de mayo, 16 de "
            "septiembre, 12 de octubre, 20 de noviembre y 25 de "
            "diciembre, asi como aquellos en que se suspendan las "
            "labores en el organo jurisdiccional. Este articulo "
            "califica los 'quince dias' del articulo 17 como dias "
            "habiles. El computo del plazo de amparo se hace con "
            "exclusion de los dias listados aqui mas los feriados "
            "oficiales aplicables."
        ),
    },
    "61": {
        "title": "Improcedencia del juicio de amparo",
        "use": (
            "El juicio de amparo es improcedente en los supuestos "
            "listados en las fracciones I a XXIII del articulo 61. "
            "Para resoluciones de la Secretaria, las causales mas "
            "relevantes a vigilar son: actos consumados de modo "
            "irreparable, falta de interes juridico o legitimo, "
            "consentimiento del acto (no impugnarlo en el plazo de "
            "15 dias), y cosa juzgada. El MCP no transcribe el "
            "catalogo completo; alerta al usuario de que debe "
            "verificar que su caso no caiga en ninguna causal."
        ),
    },
    "107": {
        "title": "Procedencia del amparo indirecto",
        "use": (
            "El amparo indirecto procede: fraccion II contra actos u "
            "omisiones de autoridades distintas de los tribunales "
            "judiciales, administrativos o del trabajo; fraccion III "
            "contra actos, omisiones o resoluciones provenientes de "
            "un procedimiento administrativo seguido en forma de "
            "juicio. La resolucion de la Secretaria encuadra en ambas "
            "fracciones, siendo la III la mas precisa por tratarse de "
            "un procedimiento con pruebas, alegatos y resolucion "
            "definitiva. El articulo 51 de la LFPDPPP confirma "
            "expresamente la procedencia del amparo."
        ),
    },
    "125": {
        "title": "Suspension del acto reclamado",
        "use": (
            "La suspension del acto reclamado se decretara de oficio "
            "o a peticion del quejoso. En el contexto ARCO, si la "
            "Secretaria confirma una negativa del responsable y el "
            "tratamiento de datos continua, el titular puede solicitar "
            "la suspension para que cesen los efectos del acto "
            "mientras se resuelve el amparo. Los requisitos para que "
            "proceda la suspension a peticion de parte estan en el "
            "articulo 128 de esta Ley."
        ),
    },
    "128": {
        "title": "Requisitos para que proceda la suspension",
        "use": (
            "Con excepcion de los casos en que proceda de oficio, la "
            "suspension se decretara siempre que concurran los "
            "requisitos siguientes: I. Que la solicite el quejoso; y "
            "II. Que no se siga perjuicio al interes social ni se "
            "contravengan disposiciones de orden publico. La "
            "suspension se tramitara en incidente por separado y por "
            "duplicado. Para el caso ARCO, si la Secretaria nego la "
            "proteccion y el tratamiento persiste, debe argumentarse "
            "que la suspension no causa perjuicio social sino que "
            "protege los datos personales mientras se resuelve el "
            "fondo del amparo."
        ),
    },
}


# ── Constitucion ───────────────────────────────────────────────────────
CONSTITUTIONAL_SOURCE = (
    "Constitucion Politica de los Estados Unidos Mexicanos, "
    "DOF 05-02-1917, ultima reforma DOF 02-06-2026."
)

CONSTITUTION_ARTICLES: dict[str, dict[str, str]] = {
    "1": {
        "title": "Derechos humanos y principio pro persona",
        "use": (
            "Todas las personas gozan de los derechos humanos "
            "reconocidos en la Constitucion y en los tratados "
            "internacionales. Las normas de derechos humanos se "
            "interpretan favoreciendo en todo tiempo la proteccion "
            "mas amplia (principio pro persona). Todas las autoridades "
            "tienen obligacion de promover, respetar, proteger y "
            "garantizar los derechos humanos. En caso de duda sobre "
            "el alcance de un derecho ARCO, debe preferirse la "
            "interpretacion que maximice la proteccion del titular."
        ),
    },
    "16": {
        "title": "Proteccion constitucional de datos personales",
        "use": (
            "Parrafo segundo: Toda persona tiene derecho a la "
            "proteccion de sus datos personales, al acceso, "
            "rectificacion y cancelacion de los mismos, asi como "
            "a manifestar su oposicion, en los terminos que fije "
            "la ley. La ley establecera los supuestos de excepcion "
            "por razones de seguridad nacional, orden publico, "
            "seguridad y salud publicas o para proteger derechos "
            "de terceros. Este es el fundamento constitucional "
            "directo de los derechos ARCO y de los limites del "
            "articulo 3 de la LFPDPPP."
        ),
    },
    "103": {
        "title": "Procedencia del amparo por violacion de derechos humanos",
        "use": (
            "Los Tribunales de la Federacion resuelven toda "
            "controversia que se suscite por normas generales, "
            "actos u omisiones de la autoridad que violen los "
            "derechos humanos reconocidos en la Constitucion y "
            "tratados internacionales (fraccion I). La resolucion "
            "de la Secretaria que viole el derecho a la proteccion "
            "de datos personales (art. 16 constitucional) es "
            "impugnable via amparo por esta via."
        ),
    },
}
