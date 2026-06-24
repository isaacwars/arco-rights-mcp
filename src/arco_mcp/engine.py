"""Core legal validation and drafting engine for ARCO requests."""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from .types import CaseSummary

from .law import (
    ARTICLES,
    AUTHORITY,
    BASE_ARTICLES,
    DECREE_SOURCE,
    GENERAL_LIMIT_ARTICLES,
    GENERAL_PROVISIONS,
    PENAL_ARTICLES,
    REGULATION_ARTICLES,
    RIGHTS,
    SANCTION_ARTICLES,
    SECRETARIA_ARTICLES,
    SELF_REGULATION_ARTICLES,
    SENSITIVE_ARTICLES,
    SOURCE_PROVENANCE_RULES,
    TRANSFER_ARTICLES,
    VALID_RIGHTS,
)
from .escalation import (
    AMPARO_ARTICLES,
    AMPARO_SOURCE,
    CONSTITUTION_ARTICLES,
    CONSTITUTIONAL_SOURCE,
    LFPA_ARTICLES,
    LFPA_SOURCE,
)

# ── Version tracing ────────────────────────────────────────────────
_DECREE_DATE = "2025-03-20"
_ENGINE_VERSION = "0.2.0"

# ── Legal Relationship Graph — semantic cross-references between articles ──
# Eliminates hallucination, ambiguity, and misapplication by defining
# the exact relationships between every article that interacts with another.
# Relationship types:
#   requires      — A cannot be applied without B (foundation)
#   limits        — A restricts the scope of B
#   overrides     — A prevails over B when in conflict
#   complements   — A expands or details B
#   excepts       — A provides exceptions to B's general rule
#   procedural    — A is the next procedural step after B
#   defines       — A defines a term used in B

LEGAL_GRAPH: dict[str, list[dict[str, str]]] = {
    # ── Chapter I: General Provisions (1-4) ──
    "1": [  # Objeto de la Ley
        {"target": "5", "type": "requires", "reason": "Los principios del art. 5 operativizan el objeto de proteccion del art. 1"},
        {"target": "16", "type": "complements", "reason": "El art. 16 CPEUM eleva el objeto de la ley a rango constitucional"},
    ],
    "2": [  # Definiciones
        {"target": "7", "type": "defines", "reason": "Define 'consentimiento' usado en el art. 7"},
        {"target": "8", "type": "defines", "reason": "Define 'datos sensibles' usado en el art. 8"},
        {"target": "35", "type": "defines", "reason": "Define 'transferencia' usado en los arts. 35-36"},
        {"target": "28", "type": "defines", "reason": "Define 'titular' y 'responsable' usados en el art. 28"},
    ],
    "3": [  # Limites a derechos ARCO
        {"target": "22", "type": "limits", "reason": "Los limites del art. 3 restringen el alcance del acceso (art. 22)"},
        {"target": "23", "type": "limits", "reason": "Los limites del art. 3 restringen el alcance de la rectificacion"},
        {"target": "24", "type": "limits", "reason": "Los limites del art. 3 restringen el alcance de la cancelacion"},
        {"target": "25", "type": "limits", "reason": "El art. 3 exige interpretacion restrictiva de las excepciones del art. 25"},
        {"target": "26", "type": "limits", "reason": "Los limites del art. 3 restringen el alcance de la oposicion"},
        {"target": "4", "type": "complements", "reason": "Art. 4 detalla la interpretacion restrictiva de limites"},
    ],
    "4": [  # Interpretacion restrictiva de limites
        {"target": "3", "type": "complements", "reason": "Operativiza los limites del art. 3 con principio de interpretacion restrictiva"},
        {"target": "25", "type": "overrides", "reason": "Las excepciones del art. 25 deben leerse a la luz del art. 4: no pueden vaciar el derecho"},
    ],

    # ── Chapter II: Principles (5-20) ──
    "5": [  # Principios
        {"target": "6", "type": "requires", "reason": "El principio de licitud (art. 6) es parte de los principios del art. 5"},
        {"target": "11", "type": "requires", "reason": "El principio de finalidad (art. 11) deriva de los principios del art. 5"},
        {"target": "10", "type": "requires", "reason": "El principio de calidad (art. 10) deriva de los principios del art. 5"},
        {"target": "13", "type": "requires", "reason": "El principio de responsabilidad (art. 13) deriva de los principios del art. 5"},
    ],
    "6": [  # Licitud
        {"target": "7", "type": "requires", "reason": "El consentimiento (art. 7) es el mecanismo principal de licitud del art. 6"},
        {"target": "9", "type": "excepts", "reason": "El art. 9 enumera los casos en que no se requiere consentimiento"},
        {"target": "R44", "type": "complements", "reason": "R44 define cuando hay dolo/mala fe/negligencia, violando la licitud del art. 6"},
    ],
    "7": [  # Consentimiento
        {"target": "8", "type": "complements", "reason": "El art. 8 detalla consentimiento expreso requerido por el art. 7 para datos sensibles"},
        {"target": "9", "type": "excepts", "reason": "Casos en que el consentimiento del art. 7 no es necesario"},
        {"target": "21", "type": "requires", "reason": "El consentimiento es presupuesto para el ejercicio ARCO del art. 21"},
        {"target": "R44", "type": "complements", "reason": "R44 prohibe obtener consentimiento por medios enganosos"},
    ],
    "8": [  # Datos sensibles
        {"target": "7", "type": "requires", "reason": "Requiere consentimiento expreso y por escrito del art. 7"},
        {"target": "12", "type": "complements", "reason": "Prohibe crear bases de datos sensibles sin justificacion (art. 12)"},
        {"target": "59", "type": "complements", "reason": "Sancion agravada cuando se trata de datos sensibles"},
    ],
    "11": [  # Principio de finalidad
        {"target": "15", "type": "requires", "reason": "El aviso de privacidad (art. 15) debe informar las finalidades del art. 11"},
        {"target": "35", "type": "limits", "reason": "Las transferencias del art. 35 deben limitarse a las finalidades del art. 11"},
        {"target": "36", "type": "limits", "reason": "Las transferencias sin consentimiento deben sujetarse al principio de finalidad"},
    ],
    "15": [  # Aviso de privacidad
        {"target": "11", "type": "requires", "reason": "Debe distinguir finalidades necesarias vs secundarias segun art. 11"},
        {"target": "16", "type": "complements", "reason": "Art. 16 regula como poner el aviso a disposicion"},
        {"target": "35", "type": "requires", "reason": "Las transferencias deben estar informadas en el aviso del art. 15"},
        {"target": "58", "type": "complements", "reason": "No tener aviso o tenerlo deficiente es infraccion del art. 58"},
    ],

    # ── Chapter III: ARCO Rights (21-26) ──
    "21": [  # Habilitacion ARCO
        {"target": "22", "type": "complements", "reason": "Habilita el derecho de acceso"},
        {"target": "23", "type": "complements", "reason": "Habilita el derecho de rectificacion"},
        {"target": "24", "type": "complements", "reason": "Habilita el derecho de cancelacion"},
        {"target": "26", "type": "complements", "reason": "Habilita el derecho de oposicion"},
        {"target": "28", "type": "requires", "reason": "El art. 28 establece como se ejerce lo habilitado por el art. 21"},
        {"target": "34", "type": "complements", "reason": "La gratuidad del art. 34 aplica a todos los derechos del art. 21"},
    ],
    "22": [  # Acceso
        {"target": "28", "type": "requires", "reason": "El acceso se ejerce mediante solicitud conforme al art. 28"},
        {"target": "31", "type": "requires", "reason": "La respuesta al acceso se rige por los plazos del art. 31"},
        {"target": "3", "type": "limits", "reason": "Sujeto a los limites del art. 3"},
    ],
    "23": [  # Rectificacion
        {"target": "28", "type": "requires", "reason": "Se ejerce mediante solicitud conforme al art. 28"},
        {"target": "30", "type": "complements", "reason": "El art. 30 detalla el procedimiento de rectificacion"},
        {"target": "31", "type": "requires", "reason": "La respuesta se rige por los plazos del art. 31"},
    ],
    "24": [  # Cancelacion
        {"target": "25", "type": "complements", "reason": "El art. 25 enumera las excepciones a la cancelacion del art. 24"},
        {"target": "28", "type": "requires", "reason": "Se ejerce mediante solicitud conforme al art. 28"},
        {"target": "31", "type": "requires", "reason": "La respuesta se rige por los plazos del art. 31"},
    ],
    "25": [  # Excepciones a cancelacion
        {"target": "24", "type": "limits", "reason": "Limita el alcance de la cancelacion del art. 24"},
        {"target": "3", "type": "limits", "reason": "El art. 3 exige interpretacion restrictiva del art. 25"},
        {"target": "4", "type": "limits", "reason": "El art. 4 prohíbe que las excepciones vacíen el contenido esencial"},
    ],
    "26": [  # Oposicion
        {"target": "28", "type": "requires", "reason": "Se ejerce mediante solicitud conforme al art. 28"},
        {"target": "31", "type": "requires", "reason": "La respuesta se rige por los plazos del art. 31"},
        {"target": "36", "type": "overrides", "reason": "La oposicion expresa del art. 26 deja sin efectos la excepcion de transferencia a afiliadas del art. 36-III"},
    ],

    # ── Chapter IV: Procedure (27-34) ──
    "28": [  # Requisitos de solicitud
        {"target": "21", "type": "requires", "reason": "Operativiza el ejercicio ARCO habilitado por el art. 21"},
        {"target": "29", "type": "complements", "reason": "El responsable debe designar persona/departamento para recibir solicitudes del art. 28"},
        {"target": "32", "type": "complements", "reason": "Prevencion por informacion insuficiente en solicitud del art. 28"},
        {"target": "33", "type": "complements", "reason": "Causas de improcedencia de la solicitud del art. 28"},
    ],
    "29": [  # Persona o departamento designado
        {"target": "28", "type": "complements", "reason": "Recepcion de las solicitudes del art. 28"},
        {"target": "30", "type": "complements", "reason": "Medios para presentar solicitudes"},
    ],
    "31": [  # Plazos
        {"target": "28", "type": "procedural", "reason": "Plazo para responder a la solicitud del art. 28"},
        {"target": "32", "type": "procedural", "reason": "Ampliacion del plazo del art. 31 por prevencion del art. 32"},
        {"target": "40", "type": "procedural", "reason": "Vencido el plazo del art. 31 sin respuesta, procede solicitud de proteccion ante Secretaria (art. 40)"},
    ],
    "32": [  # Prevencion
        {"target": "28", "type": "complements", "reason": "Si la solicitud del art. 28 esta incompleta, se previene por una sola vez"},
        {"target": "31", "type": "complements", "reason": "La prevencion interrumpe el plazo del art. 31"},
    ],
    "33": [  # Improcedencia
        {"target": "28", "type": "complements", "reason": "Causas por las que la solicitud del art. 28 puede ser improcedente"},
        {"target": "3", "type": "limits", "reason": "La improcedencia debe interpretarse conforme a los limites del art. 3"},
    ],
    "34": [  # Gratuidad
        {"target": "21", "type": "complements", "reason": "El ejercicio ARCO del art. 21 es gratuito"},
        {"target": "31", "type": "complements", "reason": "La respuesta del art. 31 es gratuita, salvo costos de reproduccion/envio justificados"},
    ],

    # ── Chapter V: Transfers (35-36) ──
    "35": [  # Transferencias
        {"target": "11", "type": "requires", "reason": "Las transferencias deben sujetarse al principio de finalidad del art. 11"},
        {"target": "15", "type": "requires", "reason": "Las transferencias deben comunicarse en el aviso del art. 15"},
        {"target": "36", "type": "complements", "reason": "El art. 36 detalla los supuestos de transferencia sin consentimiento"},
    ],
    "36": [  # Transferencias sin consentimiento
        {"target": "35", "type": "complements", "reason": "Detalla excepciones a la regla general del art. 35"},
        {"target": "26", "type": "limits", "reason": "La oposicion del art. 26 puede dejar sin efecto la excepcion de afiliadas del art. 36-III"},
        {"target": "R68", "type": "complements", "reason": "R68: toda transferencia requiere ser informada en el aviso"},
        {"target": "R69", "type": "complements", "reason": "R69: carga de la prueba recae en el responsable que transfiere"},
        {"target": "R70", "type": "complements", "reason": "R70: normas internas vinculantes requeridas para transferencias intragrupo"},
    ],

    # ── Chapter VI: Self-regulation (37) ──
    "37": [  # Autorregulacion
        {"target": "1", "type": "complements", "reason": "Complementa el objeto de proteccion de la ley, NO lo sustituye"},
        {"target": "R86", "type": "requires", "reason": "R86: los esquemas deben estar registrados; sin registro no tienen efectos juridicos"},
        {"target": "58", "type": "complements", "reason": "El incumplimiento del esquema de autorregulacion puede constituir infraccion"},
    ],

    # ── Terminal nodes: referenced but need their own relationships ──
    "9": [  # Excepciones al consentimiento (referenciado por art. 6, 7)
        {"target": "7", "type": "excepts", "reason": "Enuncia los casos en que no se requiere el consentimiento del art. 7"},
        {"target": "6", "type": "complements", "reason": "Complementa el principio de licitud definiendo cuando no se necesita consentimiento"},
    ],
    "10": [  # Calidad y supresion
        {"target": "5", "type": "requires", "reason": "Operativiza el principio de calidad del art. 5"},
        {"target": "24", "type": "complements", "reason": "La supresion del art. 10 es la fase final tras el bloqueo de la cancelacion del art. 24"},
    ],
    "12": [  # Prohibicion de bases de datos sensibles
        {"target": "8", "type": "complements", "reason": "Prohibe crear bases de datos con datos sensibles del art. 8 sin justificacion legitima"},
        {"target": "58", "type": "complements", "reason": "La creacion de bases de datos sensibles sin justificacion es infraccion"},
    ],
    "13": [  # Responsabilidad
        {"target": "5", "type": "requires", "reason": "Operativiza el principio de responsabilidad del art. 5"},
        {"target": "58", "type": "complements", "reason": "El incumplimiento del deber de responsabilidad constituye infraccion"},
    ],
    "14": [  # Informacion por aviso
        {"target": "15", "type": "complements", "reason": "El aviso de privacidad es el medio para cumplir con el deber de informar del art. 14"},
        {"target": "7", "type": "requires", "reason": "La informacion del art. 14 es presupuesto para que el consentimiento del art. 7 sea valido"},
    ],
    "16": [  # Puesta a disposicion del aviso (referenciado por art. 1, 15)
        {"target": "15", "type": "complements", "reason": "El art. 15 define el contenido del aviso; el art. 16 define COMO ponerlo a disposicion"},
        {"target": "1", "type": "procedural", "reason": "La puesta a disposicion efectiva del aviso es condicion para la proteccion del art. 1 CPEUM"},
    ],
    "18": [  # Medidas de seguridad
        {"target": "8", "type": "requires", "reason": "Los datos sensibles del art. 8 requieren medidas de seguridad reforzadas"},
        {"target": "58", "type": "complements", "reason": "La falta de medidas de seguridad adecuadas constituye infraccion"},
    ],
    "27": [  # ARCO via representante
        {"target": "28", "type": "complements", "reason": "El representante debe cumplir los mismos requisitos del art. 28 mas acreditar la representacion"},
        {"target": "21", "type": "complements", "reason": "El representante puede ejercer los derechos ARCO habilitados por el art. 21"},
    ],
    "30": [  # Rectificacion — detalles procedimentales (referenciado por art. 23)
        {"target": "23", "type": "complements", "reason": "Detalla el procedimiento especifico de rectificacion mas alla de la solicitud generica del art. 23"},
        {"target": "28", "type": "complements", "reason": "La rectificacion requiere los elementos basicos del art. 28 mas documento soporte"},
    ],
    "38": [  # Objeto de la Secretaria (referenciado por art. 51)
        {"target": "40", "type": "procedural", "reason": "La Secretaria recibe y sustancia las solicitudes de proteccion del art. 40"},
        {"target": "54", "type": "procedural", "reason": "La Secretaria realiza verificaciones conforme al art. 54"},
        {"target": "56", "type": "procedural", "reason": "La Secretaria inicia procedimientos sancionadores conforme al art. 56"},
        {"target": "51", "type": "procedural", "reason": "Las resoluciones de la Secretaria son impugnables via amparo (art. 51)"},
    ],
    "47": [  # Improcedencia ante Secretaria (referenciado por art. 40)
        {"target": "40", "type": "limits", "reason": "Enumera las causas por las que la solicitud de proteccion del art. 40 es improcedente"},
        {"target": "48", "type": "procedural", "reason": "Ademas de improcedencia (art. 47), procede sobreseimiento (art. 48) en ciertos casos"},
    ],
    "48": [  # Sobreseimiento (referenciado por art. 40, 47)
        {"target": "40", "type": "limits", "reason": "El sobreseimiento termina el procedimiento del art. 40 por causa superveniente, sin validar al responsable"},
        {"target": "47", "type": "complements", "reason": "Complementa las causas de terminacion del procedimiento junto con la improcedencia del art. 47"},
    ],
    "55": [  # Acceso a informacion en verificacion (referenciado por art. 54)
        {"target": "54", "type": "procedural", "reason": "Detalla las facultades de acceso a informacion durante la verificacion del art. 54"},
        {"target": "56", "type": "procedural", "reason": "La informacion obtenida en verificacion (art. 55) puede derivar en sancion (art. 56)"},
    ],
    "60": [  # Graduacion de sanciones (referenciado por art. 59)
        {"target": "59", "type": "complements", "reason": "Establece los criterios para graduar las sanciones del art. 59"},
        {"target": "58", "type": "complements", "reason": "La graduacion del art. 60 toma en cuenta la naturaleza de la infraccion del art. 58"},
    ],
    "R86": [  # Registro de autorregulacion (referenciado por art. 37)
        {"target": "37", "type": "complements", "reason": "Los esquemas del art. 37 solo tienen efectos si estan registrados conforme al R86"},
        {"target": "58", "type": "complements", "reason": "Operar un esquema de autorregulacion sin registro puede constituir infraccion"},
    ],

    # ── Constitution ──
    "CPEUM-16": [
        {"target": "1", "type": "requires", "reason": "El art. 16 constitucional es el fundamento supremo del derecho a la proteccion de datos personales"},
        {"target": "21", "type": "requires", "reason": "Los derechos ARCO del art. 21 son concrecion legislativa de la proteccion del art. 16 CPEUM"},
        {"target": "51", "type": "requires", "reason": "El amparo del art. 51 es la via para tutelar judicialmente el derecho del art. 16 CPEUM"},
    ],
    "CPEUM-1": [
        {"target": "CPEUM-16", "type": "complements", "reason": "El principio pro persona del art. 1 obliga a interpretar el art. 16 en el sentido mas favorable al titular"},
        {"target": "3", "type": "limits", "reason": "Los limites del art. 3 LFPDPPP deben interpretarse conforme al principio pro persona del art. 1 CPEUM"},
    ],
    "CPEUM-103": [
        {"target": "51", "type": "requires", "reason": "Fundamento constitucional del juicio de amparo del art. 51 LFPDPPP"},
        {"target": "CPEUM-16", "type": "complements", "reason": "El art. 103 habilita la via judicial para proteger el derecho del art. 16"},
    ],

    # ── LFPA (Ley Federal de Procedimiento Administrativo) ──
    "LFPA-1": [
        {"target": "LFPA-3", "type": "requires", "reason": "Supletoriedad de la LFPA en el procedimiento ante la Secretaria"},
        {"target": "40", "type": "complements", "reason": "La solicitud de proteccion del art. 40 LFPDPPP se rige supletoriamente por la LFPA"},
    ],
    "LFPA-3": [
        {"target": "40", "type": "complements", "reason": "Define los elementos del acto administrativo que debe cumplir la resolucion de la Secretaria"},
        {"target": "LFPA-35", "type": "procedural", "reason": "Las notificaciones de la Secretaria se rigen por el art. 35 LFPA"},
    ],
    "LFPA-35": [
        {"target": "LFPA-3", "type": "procedural", "reason": "Detalla los requisitos de las notificaciones administrativas"},
        {"target": "31", "type": "complements", "reason": "Complementa el regimen de notificaciones del art. 31 LFPDPPP en sede administrativa"},
    ],
    "LFPA-38": [
        {"target": "LFPA-39", "type": "procedural", "reason": "Recurso de revision contra actos administrativos, paso previo opcional al amparo indirecto"},
        {"target": "40", "type": "procedural", "reason": "Si la resolucion de proteccion es desfavorable, puede impugnarse via recurso de revision"},
    ],
    "LFPA-39": [
        {"target": "51", "type": "procedural", "reason": "Agotado el recurso de revision LFPA, procede amparo indirecto del art. 51"},
        {"target": "LFPA-38", "type": "procedural", "reason": "El recurso de revision suspende la definitividad para efectos del amparo"},
    ],

    # ── Ley de Amparo ──
    "LA-17": [
        {"target": "51", "type": "complements", "reason": "Plazo de 15 DIAS HABILES para promover amparo contra resolucion de la Secretaria"},
        {"target": "LA-19", "type": "complements", "reason": "El computo del plazo del art. 17 LA es en dias habiles conforme al art. 19 LA"},
    ],
    "LA-19": [
        {"target": "LA-17", "type": "complements", "reason": "Confirma que el plazo de amparo se computa en DIAS HABILES"},
        {"target": "31", "type": "complements", "reason": "Coherencia: tanto plazos ARCO (art. 31 LFPDPPP) como plazos de amparo son en dias habiles"},
    ],
    "LA-107": [
        {"target": "51", "type": "complements", "reason": "Define que el amparo contra resoluciones de la Secretaria es INDIRECTO ante Juzgado de Distrito"},
        {"target": "LA-17", "type": "procedural", "reason": "El plazo del art. 17 LA aplica al amparo indirecto del art. 107 LA"},
    ],
    "LA-125": [
        {"target": "LA-107", "type": "complements", "reason": "Regula la suspension del acto reclamado en amparo indirecto"},
        {"target": "LA-128", "type": "complements", "reason": "La suspension no debe perjudicar el interes social ni contravenir disposiciones de orden publico"},
    ],
    "LA-128": [
        {"target": "LA-125", "type": "complements", "reason": "Establece los requisitos para que proceda la suspension en amparo indirecto"},
    ],
    "LA-61": [
        {"target": "LA-107", "type": "complements", "reason": "Define las causales de improcedencia del amparo, incluyendo definitividad"},
        {"target": "LFPA-38", "type": "procedural", "reason": "El recurso LFPA debe agotarse antes del amparo por principio de definitividad"},
    ],

    # ── Chapter VII-VIII: Secretaria y Procedimientos (38-55) ──
    "40": [  # Solicitud de proteccion de datos
        {"target": "31", "type": "procedural", "reason": "Paso siguiente cuando vence el plazo del art. 31 sin respuesta"},
        {"target": "41", "type": "procedural", "reason": "Requisitos de la solicitud de proteccion"},
        {"target": "47", "type": "complements", "reason": "Causas de improcedencia de la solicitud de proteccion"},
        {"target": "48", "type": "complements", "reason": "Causas de sobreseimiento"},
    ],
    "41": [  # Requisitos solicitud proteccion
        {"target": "40", "type": "procedural", "reason": "Detalla los requisitos para la solicitud del art. 40"},
        {"target": "28", "type": "complements", "reason": "Debe acompanar copia de la solicitud ARCO original (art. 28) y constancia de recepcion"},
    ],
    "51": [  # Amparo
        {"target": "54", "type": "procedural", "reason": "El amparo procede contra resoluciones de verificacion del art. 54"},
        {"target": "38", "type": "procedural", "reason": "El amparo procede contra cualquier resolucion de la Secretaria (art. 38)"},
    ],
    "54": [  # Verificacion
        {"target": "40", "type": "procedural", "reason": "La verificacion puede derivar de una solicitud de proteccion del art. 40"},
        {"target": "55", "type": "complements", "reason": "El art. 55 regula el acceso a informacion durante la verificacion"},
        {"target": "56", "type": "procedural", "reason": "Si en verificacion hay incumplimiento, inicia procedimiento sancionador (art. 56)"},
    ],

    # ── Chapter IX-XI: Sanctions (56-64) ──
    "56": [  # Inicio procedimiento sancionador
        {"target": "54", "type": "procedural", "reason": "Puede iniciar tras verificacion del art. 54"},
        {"target": "58", "type": "procedural", "reason": "Determina las infracciones que seran sancionadas"},
        {"target": "59", "type": "procedural", "reason": "Establece las sanciones aplicables"},
    ],
    "58": [  # Infracciones
        {"target": "59", "type": "procedural", "reason": "El art. 59 establece las sanciones para las infracciones del art. 58"},
        {"target": "5", "type": "requires", "reason": "Muchas infracciones son violaciones a los principios del art. 5"},
        {"target": "15", "type": "requires", "reason": "Infracciones relacionadas con el aviso de privacidad del art. 15"},
        {"target": "28", "type": "requires", "reason": "Infracciones por no atender solicitudes del art. 28"},
    ],
    "59": [  # Sanciones
        {"target": "58", "type": "procedural", "reason": "Sanciona las infracciones del art. 58"},
        {"target": "8", "type": "complements", "reason": "Sancion se duplica cuando involucra datos sensibles del art. 8"},
        {"target": "60", "type": "complements", "reason": "Graduacion de sanciones del art. 59"},
    ],

    # ── Regulation 2011 key interactions ──
    "R44": [  # Prohibicion de medios enganosos
        {"target": "6", "type": "complements", "reason": "Define cuando hay violacion al principio de licitud del art. 6 LFPDPPP"},
        {"target": "7", "type": "complements", "reason": "Define cuando el consentimiento del art. 7 fue obtenido fraudulentamente"},
        {"target": "58", "type": "complements", "reason": "Medios enganosos pueden constituir infraccion del art. 58"},
    ],
    "R68": [  # Consentimiento para transferencias en aviso
        {"target": "35", "type": "complements", "reason": "Refuerza que toda transferencia debe estar en el aviso"},
        {"target": "36", "type": "complements", "reason": "Aplica tambien a transferencias sin consentimiento"},
    ],
    "R69": [  # Carga de la prueba en transferencias
        {"target": "35", "type": "complements", "reason": "El responsable que transfiere carga con la prueba de cumplimiento"},
        {"target": "36", "type": "complements", "reason": "Aplica a todos los supuestos de transferencia"},
    ],
    "R70": [  # Normas internas vinculantes
        {"target": "36", "type": "complements", "reason": "Exige normas vinculantes para la transferencia intragrupo del art. 36-III"},
    ],
    "R91": [  # Canales de atencion como canal ARCO
        {"target": "28", "type": "complements", "reason": "Amplia los medios validos para presentar solicitudes ARCO"},
        {"target": "30", "type": "complements", "reason": "Compatible con el art. 30 sobre medios electronicos"},
    ],
}

def build_trace() -> dict[str, str]:
    """Return metadata for every output: what version of the law was used."""
    return {
        "lfpdpPP_decree_date": _DECREE_DATE,
        "engine_version": _ENGINE_VERSION,
        "lfpa_source": "DOF 04-08-1994, ultima reforma DOF 14-11-2025",
        "amparo_source": "DOF 02-04-2013",
        "constitution_source": "DOF 05-02-1917, ultima reforma DOF 02-06-2026",
    }


# Mapping: field path → why it's required (article + rationale for LLM reasoning)
_REQUIRED_BY: dict[str, str] = {
    "titular.nombre_completo": "art. 28 frac. I LFPDPPP: nombre del titular",
    "titular.identificacion.tipo": "art. 28 frac. II LFPDPPP: documentos que acrediten identidad",
    "titular.identificacion.vigente": "art. 28 frac. II LFPDPPP: identificacion debe ser vigente para acreditar identidad",
    "titular.identificacion.se_adjunta_copia": "art. 28 frac. II LFPDPPP: debe acompanarse copia de la identificacion",
    "solicitud.ciudad": "art. 28 frac. I LFPDPPP: domicilio del titular para recibir notificaciones",
    "solicitud.fecha": "art. 31 LFPDPPP: la fecha determina el inicio del computo de plazos",
    "medio_notificaciones.valor": "art. 28 frac. I LFPDPPP: medio para recibir notificaciones",
    "responsable.naturaleza": "art. 1 LFPDPPP: solo aplica a sujetos regulados privados",
    "responsable.nombre_legal": "art. 28 LFPDPPP: solicitud debe dirigirse al responsable; art. 15 LFPDPPP: identidad del responsable en el aviso",
    "responsable.domicilio": "art. 28 LFPDPPP: domicilio del responsable; art. 15 LFPDPPP: domicilio en el aviso",
    "responsable.canal_arco": "art. 28 LFPDPPP: medio de recepcion; art. 15 LFPDPPP: mecanismos ARCO en el aviso",
    "responsable.fuente_aviso_privacidad": "art. 15 LFPDPPP: el aviso de privacidad es la unica fuente primaria de identidad, domicilio y canal ARCO",
    "relacion_juridica.descripcion": "art. 28 frac. V LFPDPPP: elementos que faciliten localizacion de datos",
    "datos_personales": "art. 28 frac. III LFPDPPP: descripcion clara y precisa de los datos (salvo acceso puro)",
    "derechos_solicitados": "art. 28 frac. IV LFPDPPP: descripcion del derecho ARCO ejercido",
    "responsable.fuente_aviso_privacidad.tipo": "art. 15 LFPDPPP: el aviso debe estar disponible en formato verificable (URL oficial, PDF, HTML o impreso)",
    "responsable.fuente_aviso_privacidad.referencia": "art. 15 LFPDPPP: debe identificarse la fuente exacta del aviso (URL, ruta o folio) para verificar identidad del responsable",
    "responsable.fuente_aviso_privacidad.fecha_consulta": "art. 15 LFPDPPP: la fecha de consulta documenta la vigencia del aviso; avisos no reconsultados pueden contener datos desactualizados",
    "responsable.fuente_aviso_privacidad.es_fuente_oficial": "art. 15 LFPDPPP: solo el aviso del canal oficial del responsable es fuente primaria valida; fuentes de terceros no garantizan vigencia",
}

# Rationale for blocker codes — why each validation rule exists, with legal basis
_BLOCKER_RATIONALE: dict[str, str] = {
    "wrong_legal_regime": "art. 1 LFPDPPP: esta Ley solo aplica a sujetos regulados privados; si el responsable es autoridad publica debe usarse la ley general correspondiente",
    "expired_id": "art. 28 frac. II LFPDPPP: la identificacion debe acreditar identidad; si esta vencida, el responsable puede negar por falta de acreditacion",
    "identity_not_attached": "art. 28 frac. II LFPDPPP: deben acompanarse documentos que acrediten identidad del titular",
    "no_right_selected": "art. 28 frac. IV LFPDPPP: debe describirse el derecho ARCO o lo solicitado",
    "data_requires_sensitive_treatment": "art. 8 LFPDPPP: datos sensibles requieren consentimiento expreso y por escrito; si no se marcan como sensibles, se omite esta proteccion reforzada",
    "biometric_requires_sensitive_treatment": "art. 8 LFPDPPP: los datos biometricos son inherentemente sensibles; su tratamiento exige consentimiento expreso y por escrito",
    "health_requires_sensitive_treatment": "art. 8 LFPDPPP: los datos de salud son inherentemente sensibles; su tratamiento exige consentimiento expreso y por escrito",
    "missing_data_description": "art. 28 frac. III LFPDPPP: debe describirse clara y precisamente los datos personales (salvo acceso puro)",
    "weak_opposition_damage_statement": "art. 26 frac. I LFPDPPP: la oposicion por causa legitima requiere que la persistencia del tratamiento cause un dano o perjuicio concreto; un dano generico o de pocas palabras no cumple este estandar y puede ser desestimado",
    "missing_efectos_juridicos_automatizado": "art. 26 frac. II LFPDPPP: la oposicion por tratamiento automatizado requiere describir los efectos juridicos no deseados o la afectacion significativa",
    "wrong_or_unidentified_legal_entity": "art. 28 LFPDPPP: la solicitud debe dirigirse al responsable; art. 15 LFPDPPP: la identidad del responsable debe tomarse del aviso de privacidad",
    "trade_name_only": "art. 15 LFPDPPP: el aviso de privacidad identifica al responsable legal, no al nombre comercial; dirigir la solicitud a una marca o nombre comercial permite al responsable alegar que no iba dirigida a el",
    "no_privacy_notice_source": "art. 15 LFPDPPP: el aviso de privacidad es la unica fuente primaria de identidad, domicilio y canal ARCO del responsable",
    "wrong_or_missing_arco_channel": "art. 28 LFPDPPP: la solicitud debe enviarse al canal ARCO designado; art. 15 frac. V LFPDPPP: el aviso debe contener los mecanismos ARCO",
    "non_primary_privacy_notice_type": "art. 15 LFPDPPP: el aviso debe ser una fuente primaria verificable (URL oficial, PDF, HTML del responsable o documento impreso)",
    "privacy_notice_not_confirmed_official": "art. 15 LFPDPPP: solo el aviso de privacidad del canal oficial del responsable es fuente primaria valida; fuentes de terceros pueden contener datos desactualizados",
    "placeholder_privacy_notice_reference": "art. 15 LFPDPPP: la referencia del aviso debe ser verificable; un placeholder no permite verificar la identidad del responsable",
    "third_party_source_used_as_notice": "art. 15 LFPDPPP: la fuente del aviso debe ser oficial; fuentes de terceros (GitHub, blogs, Wikipedia) no sustituyen el aviso del responsable",
    "official_url_domain_mismatch": "art. 15 LFPDPPP: si la fuente se declara como URL oficial, el dominio debe coincidir con el dominio esperado del responsable",
    "missing_receipt_for_secretaria": "art. 40 LFPDPPP: para presentar solicitud de proteccion de datos ante la Secretaria debe acompanarse constancia que pruebe la fecha de presentacion ante el responsable",
    "invalid_data_personales_format": "art. 28 frac. III LFPDPPP: los datos personales deben describirse en una lista de objetos con descripcion, categoria y campo sensible",
    "invalid_privacy_notice_source": "art. 15 LFPDPPP: la fuente del aviso debe ser un objeto verificable con tipo, referencia, fecha de consulta y confirmacion de oficialidad",
    "future_consultation_date": "art. 15 LFPDPPP: la fecha de consulta del aviso debe ser anterior o igual a la fecha actual; una fecha futura invalida la verificacion de vigencia",
    "invalid_or_missing_consultation_date": "art. 15 LFPDPPP: la fecha de consulta del aviso en formato ISO YYYY-MM-DD es indispensable para verificar su vigencia",
    "invalid_official_url": "art. 15 LFPDPPP: si el aviso se consulto como URL oficial, la referencia debe ser una URL completa con dominio verificable",
    "branch_scope_defense": "art. 28 LFPDPPP: la solicitud debe dirigirse al responsable legal, no a una sucursal; incluir folio/contrato evita que acoten el alcance",
    "weak_legal_relationship": "art. 28 frac. V LFPDPPP: sin relacion juridica clara, el responsable puede alegar imposibilidad de localizar los datos",
    "legal_name_equals_trade_name": "art. 15 LFPDPPP: la razon social y el nombre comercial no deben coincidir; verifica el aviso para identificar al responsable legal",
    "rfc_format_suspicious": "art. 28 LFPDPPP: aunque el RFC no es requisito obligatorio, un formato sospechoso puede indicar que se usa un identificador fiscal incorrecto",
    "overbroad_all_arco": "art. 21 LFPDPPP: ejercer todos los derechos ARCO simultaneamente es valido pero puede parecer generico; cada derecho debe tener su propia causa y peticion concreta",
    "cancellation_exceptions": "art. 25 LFPDPPP: la cancelacion tiene excepciones legales; no pedir borrado inmediato absoluto sin contemplar bloqueo previo",
    "opposition_legal_obligation_limit": "art. 26 LFPDPPP: la oposicion no procede si el tratamiento es necesario para cumplir una obligacion legal; debe delimitarse a finalidades secundarias",
    "not_autonomous_arco": "arts. 21 y 26 LFPDPPP: limitacion de uso/divulgacion y revocacion de consentimiento NO son derechos ARCO autonomos; deben formularse como peticiones complementarias",
    "contextual_high_risk_data": "art. 8 LFPDPPP: datos de ubicacion, patrimoniales o financieros pueden ser sensibles segun contexto, volumen, finalidad y riesgo; evaluar si requieren proteccion reforzada",
    "receipt_needed_after_sending": "art. 40 LFPDPPP: para escalar ante la Secretaria se requiere acreditar la fecha de presentacion de la solicitud ARCO ante el responsable",
    "stale_privacy_notice_source": "art. 15 LFPDPPP: un aviso consultado hace mas de 180 dias puede contener datos desactualizados de razon social, domicilio o canal ARCO",
    "privacy_notice_should_be_rechecked": "art. 15 LFPDPPP: un aviso con mas de 30 dias de antiguedad conviene revalidarlo para confirmar que no ha cambiado",
    "rfc_recommended_for_disambiguation": "art. 28 LFPDPPP: el RFC no es obligatorio pero ayuda a distinguir entre grupo corporativo, marca, filial y sucursal",
    "case_not_ready": "el caso asociado al borrador tiene bloqueadores o faltantes criticos que impiden la redaccion; resuelve los faltantes antes de auditar",
}

PLACEHOLDER_PATTERNS = (
    r"\[[^\]]+\]",
    r"\brazon social exacta\b",
    r"\bcanal arco exacto\b",
    r"\burl del aviso\b",
    r"\bnombre completo del titular\b",
    r"\bdomicilio exacto\b",
    r"\blinea/cuenta/folio\b",
    r"\bciudad de presentacion\b",
    r"\bpendiente\b",
    r"\bpor verificar\b",
    r"\btbd\b",
    r"_{3,}",
    r"\bxx+x+\b",
    r"\bno aplica\b",
    r"\bdesconocid[oa]\b",
)

THIRD_PARTY_SOURCE_PATTERNS = (
    "wikipedia.org",
    "github.com",
    "raw.githubusercontent.com",
    "commoner-law.com",
    "sdv.com.mx",
    "executrain.com.mx",
    "zzpabogados.com",
    "elpais.com",
    "duckduckgo.com",
    "google.com/search",
    "webcache",
)

OFFICIAL_NOTICE_TYPES = {"URL oficial", "PDF", "HTML", "Documento impreso"}
STRICT_SENSITIVE_CATEGORIES = {"biometrico", "salud", "genetico", "origen_etnico_racial", "sexual", "religioso", "ideologico", "politico"}
CONTEXTUAL_HIGH_RISK_CATEGORIES = {"ubicacion", "patrimonial", "financiero"}
SENSITIVE_DESCRIPTION_PATTERNS = (
    r"\bbiom[eé]tric",
    r"\bsalud\b|\bhistorial clinico\b|\bexpediente medico\b",
    r"\bgen[eé]tic",
    r"\borigen (etnico|racial)\b",
    r"\bpreferencia sexual\b|\borientaci[oó]n sexual\b",
    r"\bcreencia religiosa\b|\bconvicci[oó]n religiosa\b",
    r"\bopini[oó]n pol[ií]tica\b|\bideolog",
)
GENERIC_DAMAGE_PATTERNS = (
    r"^da[nñ]o a mi privacidad$",
    r"^afecta mi privacidad$",
    r"^riesgo a mi privacidad$",
    r"^uso indebido$",
    r"^mal uso$",
)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.startswith("{"):
            raise ValueError(
                "El valor no es un JSON de caso ARCO valido. "
                "Debe comenzar con '{' (objeto JSON). "
                "Si estas enviando un borrador de texto, usa la herramienta "
                "'audit_draft' en lugar de 'validate_case' o 'process_case'."
            )
        if len(stripped) > 5_000_000:
            raise ValueError("JSON demasiado grande (max 5 MB).")
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalido: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("El JSON debe ser un objeto, no un array.")
        return parsed
    if isinstance(value, dict):
        return value
    raise TypeError("Se esperaba dict o JSON string.")


def _get(data: dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        return not any(re.search(pattern, text, re.IGNORECASE) for pattern in PLACEHOLDER_PATTERNS)
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in PLACEHOLDER_PATTERNS)
    return False


def _find_placeholder_paths(value: Any, prefix: str = "", depth: int = 0) -> list[str]:
    if depth > 100:
        return [f"{prefix}...(max_depth)"]
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_find_placeholder_paths(item, next_prefix, depth + 1))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.extend(_find_placeholder_paths(item, next_prefix, depth + 1))
    elif _contains_placeholder(value):
        paths.append(prefix)
    return paths


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _rights(case: dict[str, Any]) -> list[dict[str, Any]]:
    rights = case.get("derechos_solicitados", [])
    return rights if isinstance(rights, list) else []


RIGHT_DISPLAY_NAMES: dict[str, str] = {
    "acceso": "Acceso",
    "rectificacion": "Rectificacion",
    "cancelacion": "Cancelacion",
    "oposicion": "Oposicion",
    "limitacion_uso_divulgacion": "Limitacion de Uso y Divulgacion",
    "revocacion_consentimiento": "Revocacion de Consentimiento",
}


def _right_names(case: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in _rights(case):
        if isinstance(item, dict) and isinstance(item.get("tipo"), str):
            names.append(item["tipo"].strip().lower())
        elif isinstance(item, str):
            names.append(item.strip().lower())
    return names


def _right_display_names(case: dict[str, Any]) -> list[str]:
    return [RIGHT_DISPLAY_NAMES.get(n, n.title()) for n in _right_names(case)]


def _parse_iso_date(value: Any) -> _dt.date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _dt.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _data_item_requires_sensitive(item: dict[str, Any]) -> bool:
    category = str(item.get("categoria", "")).strip().lower()
    description = str(item.get("descripcion", "")).strip().lower()
    if category in STRICT_SENSITIVE_CATEGORIES:
        return True
    return any(re.search(pattern, description, re.IGNORECASE) for pattern in SENSITIVE_DESCRIPTION_PATTERNS)


def _damage_statement_is_weak(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    text = value.strip().lower()
    if _contains_placeholder(text):
        return True
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if len(words) < 6:
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in GENERIC_DAMAGE_PATTERNS)


def audit_source_provenance(case_data: dict[str, Any] | str, today: str | None = None) -> dict[str, Any]:
    """Audit whether the case facts come from legally usable sources."""
    case = _as_dict(case_data)
    responsable = case.get("responsable") or {}
    source = responsable.get("fuente_aviso_privacidad") or {}
    current_date = _parse_iso_date(today) if today else _dt.date.today()
    if current_date is None:
        current_date = _dt.date.today()

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []

    if not isinstance(source, dict):
        blockers.append({
            "code": "invalid_privacy_notice_source",
            "message": "responsable.fuente_aviso_privacidad debe ser un objeto con tipo, referencia, fecha_consulta y es_fuente_oficial.",
        })
        return {
            "ok": False,
            "source_rules": SOURCE_PROVENANCE_RULES,
            "blockers": blockers,
            "warnings": warnings,
            "checks": checks,
        }

    source_type = str(source.get("tipo", "")).strip()
    reference = str(source.get("referencia", "")).strip()
    lower_reference = reference.lower()
    consulted = _parse_iso_date(source.get("fecha_consulta"))
    official_flag = source.get("es_fuente_oficial")

    if source_type not in OFFICIAL_NOTICE_TYPES:
        blockers.append({
            "code": "non_primary_privacy_notice_type",
            "message": "La fuente del aviso debe ser URL oficial, PDF, HTML del responsable o documento impreso verificable; 'Otro' no basta para version final.",
        })
    else:
        checks.append({"ok": "fuente_aviso_privacidad.tipo", "detail": source_type})

    if official_flag is not True:
        blockers.append({
            "code": "privacy_notice_not_confirmed_official",
            "message": "Debe marcarse es_fuente_oficial=true solo tras verificar que el aviso proviene del responsable o de su canal oficial.",
        })
    else:
        checks.append({"ok": "fuente_aviso_privacidad.es_fuente_oficial", "detail": "true"})

    if not reference:
        blockers.append({
            "code": "missing_privacy_notice_reference",
            "message": "Falta referencia exacta del aviso de privacidad usado para identificar responsable, domicilio y canal ARCO.",
        })
    elif _contains_placeholder(reference):
        blockers.append({
            "code": "placeholder_privacy_notice_reference",
            "message": "La referencia del aviso conserva placeholder; debe reemplazarse por URL, ruta, folio o descripcion verificable del aviso oficial.",
        })
    elif any(pattern in lower_reference for pattern in THIRD_PARTY_SOURCE_PATTERNS):
        blockers.append({
            "code": "third_party_source_used_as_notice",
            "message": "La referencia del aviso apunta a una fuente de terceros. Usala solo como contexto; para redactar se requiere el aviso oficial del responsable.",
        })
    else:
        checks.append({"ok": "fuente_aviso_privacidad.referencia", "detail": reference})

    if consulted is None:
        blockers.append({
            "code": "invalid_or_missing_consultation_date",
            "message": "La fecha de consulta del aviso debe estar en formato ISO YYYY-MM-DD.",
        })
    else:
        days_old = (current_date - consulted).days
        if days_old < 0:
            blockers.append({
                "code": "future_consultation_date",
                "message": "La fecha de consulta del aviso no puede estar en el futuro.",
            })
        elif days_old > 180:
            warnings.append({
                "code": "stale_privacy_notice_source",
                "severity": "high",
                "message": "La fuente del aviso fue consultada hace mas de 180 dias; reconsulta antes de enviar para evitar razon social, canal o aviso desactualizado.",
            })
        elif days_old > 30:
            warnings.append({
                "code": "privacy_notice_should_be_rechecked",
                "severity": "medium",
                "message": "El aviso fue consultado hace mas de 30 dias; conviene revalidarlo antes de enviar.",
            })
        else:
            checks.append({"ok": "fuente_aviso_privacidad.fecha_consulta", "detail": consulted.isoformat()})

    legal_name = str(responsable.get("nombre_legal", "")).strip()
    trade_name = str(responsable.get("nombre_comercial", "")).strip()
    rfc = str(responsable.get("rfc", "")).strip()
    expected_domain = str(
        source.get("dominio_oficial_esperado")
        or responsable.get("dominio_oficial")
        or ""
    ).strip().lower()

    if source_type == "URL oficial" and reference and not _contains_placeholder(reference):
        parsed = urlparse(reference)
        host = (parsed.hostname or "").lower()
        if not parsed.scheme or not host:
            blockers.append({
                "code": "invalid_official_url",
                "message": "Si la fuente se declara como URL oficial, la referencia debe ser una URL completa con dominio verificable.",
            })
        elif expected_domain and not (host == expected_domain or host.endswith(f".{expected_domain}")):
            blockers.append({
                "code": "official_url_domain_mismatch",
                "message": "La URL del aviso no coincide con el dominio oficial esperado del responsable.",
            })

    if legal_name and trade_name and legal_name.casefold() == trade_name.casefold():
        warnings.append({
            "code": "legal_name_equals_trade_name",
            "severity": "high",
            "message": "La razon social coincide con el nombre comercial; verifica el aviso para evitar dirigir la solicitud a una marca o sucursal.",
        })

    if rfc and not re.fullmatch(r"[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}", rfc.upper()):
        warnings.append({
            "code": "rfc_format_suspicious",
            "severity": "medium",
            "message": "El RFC no tiene formato esperado de 12 o 13 caracteres; revisalo contra el aviso, contrato o constancia aplicable.",
        })
    elif rfc:
        checks.append({"ok": "responsable.rfc", "detail": rfc.upper()})
    else:
        warnings.append({
            "code": "rfc_recommended_for_disambiguation",
            "severity": "low",
            "message": "El RFC no es requisito general del articulo 28, pero ayuda a evitar confusion entre grupo, marca, filial o sucursal.",
        })

    return {
        "ok": not blockers,
        "source_rules": SOURCE_PROVENANCE_RULES,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "classification": "fuente_primaria_verificada" if not blockers else "fuente_no_apta_para_version_final",
    }


def article_bundle(article_ids: list[str] | None = None) -> dict[str, Any]:
    """Return controlled article summaries from all 5 legal instruments.

    Handles IDs in the formats used by legal_graph:
      "28" → LFPDPPP, "R68" → Reglamento, "CPEUM-16" → Constitucion,
      "LFPA-35" → LFPA, "LA-17" → Ley de Amparo.
    """
    ids = article_ids or sorted(ARTICLES, key=lambda x: int(x))
    articles: dict[str, dict[str, str]] = {}
    sources: set[str] = set()

    for raw in ids:
        i = str(raw)
        if i in ARTICLES:
            articles[i] = dict(ARTICLES[i])
            articles[i]["instrumento"] = "LFPDPPP 2025"
            sources.add(DECREE_SOURCE)
        elif i in REGULATION_ARTICLES:
            articles[i] = dict(REGULATION_ARTICLES[i])
            articles[i]["instrumento"] = "Reglamento LFPDPPP 2011"
            sources.add("Reglamento LFPDPPP DOF 21-12-2011")
        elif i.startswith("CPEUM-") and i.replace("CPEUM-", "") in CONSTITUTION_ARTICLES:
            num = i.replace("CPEUM-", "")
            articles[i] = dict(CONSTITUTION_ARTICLES[num])
            articles[i]["instrumento"] = "CPEUM"
            sources.add(CONSTITUTIONAL_SOURCE)
        elif i.startswith("LFPA-") and i.replace("LFPA-", "") in LFPA_ARTICLES:
            num = i.replace("LFPA-", "")
            articles[i] = dict(LFPA_ARTICLES[num])
            articles[i]["instrumento"] = "LFPA"
            sources.add(LFPA_SOURCE)
        elif i.startswith("LA-") and i.replace("LA-", "") in AMPARO_ARTICLES:
            num = i.replace("LA-", "")
            articles[i] = dict(AMPARO_ARTICLES[num])
            articles[i]["instrumento"] = "Ley de Amparo"
            sources.add(AMPARO_SOURCE)

    return {
        "source": list(sources) if sources else [DECREE_SOURCE],
        "authority_for_particulares": AUTHORITY,
        "articles": articles,
    }


def _extract_values(obj: Any, max_depth: int = 4) -> list[str]:
    """Recursively extract all leaf STRING values from a nested dict/list,
    ignoring dict keys. Skips URLs to avoid false positives."""
    if max_depth <= 0:
        return []
    if isinstance(obj, dict):
        result: list[str] = []
        for v in obj.values():
            result.extend(_extract_values(v, max_depth - 1))
        return result
    if isinstance(obj, (list, tuple)):
        result = []
        for item in obj:
            result.extend(_extract_values(item, max_depth - 1))
        return result
    if isinstance(obj, str):
        if obj.startswith("http://") or obj.startswith("https://"):
            return []
        return [obj]
    if obj is not None:
        return [str(obj)]
    return []


def select_legal_basis(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Select articles IN SCOPE for the requested rights and facts.

    This is a SURGICAL selector — each article is included only if the
    specific case context justifies it. No blanket citations.
    """
    case = _as_dict(case_data)
    selected: list[str] = []
    unknown_rights: list[str] = []
    non_arco_complements: list[str] = []

    # ── Siempre: núcleo ARCO ──
    selected.extend(["1", "3", "4"])             # objeto + limites (interpretacion restrictiva)
    selected.extend(["21", "28", "31", "34"])    # habilitacion + solicitud + plazos + gratuidad

    # ── Derechos específicos ──
    for name in _right_names(case):
        if name not in VALID_RIGHTS:
            unknown_rights.append(name)
            continue
        right_articles = RIGHTS[name]["articles"]
        selected.extend(right_articles)
        if RIGHTS[name].get("not_arco"):
            non_arco_complements.append(name)

    # ── Contextuales: solo si el caso los necesita ──

    # Art. 27 (representante): solo si hay representante legal
    if _present(_get(case, "representante")):
        if "27" not in selected:
            selected.append("27")

    # Art. 29 (departamento designado): solo si el responsable podría alegar
    # desorganización interna como defensa
    if _get(case, "responsable.canal_arco", "") or _get(case, "responsable.nombre_legal", ""):
        if "29" not in selected:
            selected.append("29")

    # Art. 32 (prevención) y 33 (improcedencia): van en sección procedimental,
    # no en el fundamento principal. Se incluyen si el caso tiene datos que
    # podrían ser objetados por el responsable.
    if "32" not in selected:
        selected.append("32")
    if "33" not in selected:
        selected.append("33")

    # ── Datos sensibles ──
    data_items = case.get("datos_personales", [])
    has_sensitive = any(
        isinstance(item, dict) and item.get("sensible") is True
        for item in (data_items if isinstance(data_items, list) else [])
    )
    if has_sensitive:
        selected.extend(SENSITIVE_ARTICLES)

    # ── Transferencias: solo si se ejerce limitación o revocación ──
    has_transfer = any(
        name in {"limitacion_uso_divulgacion", "revocacion_consentimiento"}
        for name in _right_names(case)
    ) or _present(case.get("transferencias"))
    if has_transfer:
        selected.extend(TRANSFER_ARTICLES)

    # ── Principios específicos: solo si el contexto fáctico los activa ──
    # IMPORTANTE: extraemos solo VALORES, no nombres de campo del JSON
    facts_parts: list[str] = []
    for v in _extract_values(case):
        facts_parts.append(str(v).lower())
    facts_text = " ".join(facts_parts)

    # Art. 6 (licitud): si hay indicios de medios engañosos o fraudulentos
    if any(t in facts_text for t in ("engaño", "fraudulento", "enganoso",
            "oculto", "no informado", "no informaron", "falso", "falsa")):
        if "6" not in selected:
            selected.append("6")

    # Art. 5 (principios): si hay violación de principios
    if any(t in facts_text for t in ("violacion", "principio", "irregular", "abuso")):
        if "5" not in selected:
            selected.append("5")

    # Art. 7 (consentimiento): siempre relevante para cualquier ARCO, pero
    # especialmente si hay disputa sobre consentimiento
    if any(t in facts_text for t in ("consentimiento", "consenti", "autorizo",
            "sin permiso", "no autorice", "no acepte")) or has_transfer:
        if "7" not in selected:
            selected.append("7")

    # Art. 2 (definiciones): nunca se cita en fundamento — es un glosario
    # Art. 9 (excepciones): solo si el responsable las podría invocar
    if any(t in facts_text for t in ("excepcion", "sin consentimiento", "obligacion legal")):
        if "9" not in selected:
            selected.append("9")

    # Art. 14-16 (aviso): solo si hay problemas con el aviso de privacidad
    if any(t in facts_text for t in ("no tiene aviso", "sin aviso", "aviso deficiente",
            "aviso oculto", "aviso enganoso", "no informo", "no me informaron",
            "nunca informo", "jamas informo", "no recabe", "datos sin aviso")):
        if "14" not in selected:
            selected.append("14")
        if "16" not in selected:
            selected.append("16")

    # Art. 10 (calidad): solo para rectificación
    if "rectificacion" in _right_names(case):
        if "10" not in selected:
            selected.append("10")

    # Art. 13 (responsabilidad): siempre implícito, se cita si hay incumplimiento concreto
    if any(t in facts_text for t in ("incumplimiento", "no cumplio", "violacion",
            "negligencia", "no respondio", "no contesto")):
        if "13" not in selected:
            selected.append("13")

    # ── Autorregulación: si el responsable tiene o alega tener esquema ──
    if _present(_get(case, "responsable.esquema_autorregulacion")) or any(
        t in facts_text for t in ("autorregulacion", "codigo deontologico",
                "sello de confianza", "certificacion")):
        selected.extend(SELF_REGULATION_ARTICLES)

    # ── Penal: solo si hay desencadenantes penales ──
    has_penal_trigger = any(
        token in facts_text
        for token in ("vulneracion de seguridad", "filtracion", "fuga de datos",
                      "lucro", "engaño", "engano")
    )
    if has_penal_trigger:
        selected.extend(PENAL_ARTICLES)

    # ── Autoridad y sanciones: van en sección de reserva, no en fundamento ──
    selected.extend(SECRETARIA_ARTICLES)
    selected.extend(SANCTION_ARTICLES)

    selected = _dedupe(selected)

    return {
        "ok": True,
        "source": DECREE_SOURCE,
        "authority": AUTHORITY,
        "selected_articles": selected,
        "article_summaries": {i: ARTICLES[i] for i in selected if i in ARTICLES},
        "unknown_rights": unknown_rights,
        "non_arco_complements": non_arco_complements,
        "selection_rationale": {
            "nucleo_arco": "1, 3, 4, 21, 28, 31, 34 — siempre",
            "derechos_especificos": [n for n in _right_names(case) if n in VALID_RIGHTS],
            "sensibles": has_sensitive,
            "transferencias": has_transfer,
            "penal": has_penal_trigger,
            "autorregulacion": _present(_get(case, "responsable.esquema_autorregulacion")),
        },
        "notes": [
            "Limitacion de uso/divulgacion y revocacion de consentimiento no son derechos ARCO autonomos.",
            "Las sanciones no son automaticas: dependen de infraccion concreta y procedimiento.",
            "Cada articulo se incluye SOLO si el contexto del caso lo justifica.",
        ],
    }


def build_argument_map(case_data: dict[str, Any] | str, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a claim-by-claim legal map before drafting."""
    case = _as_dict(case_data)
    if validation is None:
        validation = validate_arco_case(case)
    arguments: list[dict[str, Any]] = []

    for index, right in enumerate(_rights(case)):
        if not isinstance(right, dict):
            continue
        name = str(right.get("tipo", "")).strip().lower()
        if name not in VALID_RIGHTS:
            arguments.append({
                "index": index,
                "type": name or "desconocido",
                "status": "blocked",
                "reason": "Derecho o peticion no reconocida por la matriz controlada.",
            })
            continue

        basis = RIGHTS[name]["articles"]
        limits: list[str] = []
        proof: list[str] = ["identidad del titular", "relacion juridica o contexto de localizacion"]
        rejection_controls: list[str] = [
            "responsable legal tomado del aviso de privacidad",
            "canal ARCO oficial",
            "negativa fundada y con pruebas conforme al articulo 33",
            "si invoca articulo 3, exigir limite concreto: seguridad nacional, orden, seguridad o salud publicos, o derechos de terceros",
        ]

        if name == "acceso":
            scope = "Conocer datos personales en posesion del responsable y condiciones/generales de tratamiento."
            proof.append("elementos para localizar registros si existen cuenta, folio, linea o contrato")
            limits.append("El acceso se cumple por puesta a disposicion, copias simples, documentos electronicos u otro medio del aviso.")
        elif name == "rectificacion":
            scope = "Corregir datos inexactos, incompletos o no actualizados."
            proof.extend(["dato actual incorrecto", "dato correcto", "documento soporte"])
            limits.append("Sin documento soporte, el responsable puede negar por falta de acreditacion material.")
        elif name == "cancelacion":
            scope = "Solicitar cancelacion, bloqueo previo y supresion posterior de datos no necesarios."
            proof.append("dato o tratamiento cuya necesidad termino o no esta justificada")
            limits.append("No procede en supuestos del articulo 25; no equivale a borrado inmediato absoluto.")
        elif name == "oposicion":
            if right.get("supuesto_oposicion") == "tratamiento_automatizado":
                scope = "Exigir cese u oposicion frente a tratamiento automatizado con efectos juridicos no deseados o afectacion significativa."
                proof.extend([
                    "descripcion del tratamiento automatizado",
                    "efecto juridico no deseado o afectacion significativa",
                    "aspectos personales evaluados sin intervencion humana",
                ])
            else:
                scope = "Exigir cese de tratamiento por causa legitima y situacion especifica."
                proof.extend(["causa legitima", "situacion especifica", "dano o perjuicio por persistencia"])
            limits.append("No procede cuando el tratamiento es necesario para cumplir una obligacion legal impuesta al responsable.")
            limits.append("El articulo 3 permite limitar derechos por seguridad nacional, orden, seguridad o salud publicos, o derechos de terceros; el responsable debe identificar el limite concreto y su necesidad.")
        elif name == "limitacion_uso_divulgacion":
            scope = "Peticion complementaria para limitar finalidades secundarias, divulgacion y transferencias no necesarias."
            proof.extend(["finalidad objetada", "base en aviso de privacidad o finalidad secundaria"])
            limits.append("No es derecho ARCO autonomo; debe formularse como complemento.")
        elif name == "revocacion_consentimiento":
            scope = "Revocar consentimiento respecto de tratamientos que dependan de el."
            proof.append("tratamiento fundado en consentimiento y no en obligacion legal o relacion juridica necesaria")
            limits.append("No tiene efectos retroactivos y no afecta tratamientos necesarios por ley o relacion juridica.")
        else:
            scope = "Peticion reconocida."

        if any(isinstance(item, dict) and item.get("sensible") is True for item in case.get("datos_personales", [])):
            rejection_controls.append("tratamiento reforzado por datos sensibles o de alto riesgo")

        arguments.append({
            "index": index,
            "type": name,
            "petition": right.get("peticion_concreta", ""),
            "scope": scope,
            "legal_basis": basis,
            "article_summaries": {article_id: ARTICLES[article_id] for article_id in basis if article_id in ARTICLES},
            "legal_limits": limits,
            "required_proof": proof,
            "rejection_controls": rejection_controls,
            "status": "ready" if validation["ready_to_draft"] else "blocked_until_case_is_ready",
        })

    return {
        "ok": True,
        "ready_to_draft": validation["ready_to_draft"],
        "validation": validation,
        "arguments": arguments,
        "general_controls": [
            "No invocar autoridad distinta de la Secretaria Anticorrupcion y Buen Gobierno para particulares bajo esta Ley.",
            "No presentar sanciones como automaticas.",
            "Separar fundamento de peticion principal, reserva ante Secretaria y sanciones.",
            "Anticipar limites del articulo 3 sin aceptar invocaciones genericas.",
            "No redactar si hay placeholders o datos no verificados.",
        ],
    }


def audit_responsable_identity(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Detect entity/channel defects that companies commonly use to reject or narrow a request."""
    case = _as_dict(case_data)
    responsable = case.get("responsable") or {}
    rel = case.get("relacion_juridica") or {}

    missing: list[str] = []
    risks: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []

    if not _present(responsable.get("nombre_legal")):
        missing.append("responsable.nombre_legal")
        risks.append({
            "code": "wrong_or_unidentified_legal_entity",
            "severity": "critical",
            "message": "Sin razon social o identidad legal tomada del aviso de privacidad, la empresa puede alegar que la solicitud se dirigio a persona distinta.",
        })
    else:
        checks.append({"ok": "responsable.nombre_legal", "detail": str(responsable.get("nombre_legal"))})

    if _present(responsable.get("nombre_comercial")) and not _present(responsable.get("nombre_legal")):
        risks.append({
            "code": "trade_name_only",
            "severity": "critical",
            "message": "El nombre comercial no basta para blindar la solicitud; debe constar el responsable legal del aviso de privacidad.",
        })

    if not _present(responsable.get("fuente_aviso_privacidad")):
        missing.append("responsable.fuente_aviso_privacidad")
        risks.append({
            "code": "no_privacy_notice_source",
            "severity": "critical",
            "message": "El aviso de privacidad vigente es la fuente primaria para identidad, domicilio y canal ARCO.",
        })

    if not _present(responsable.get("canal_arco")):
        missing.append("responsable.canal_arco")
        risks.append({
            "code": "wrong_or_missing_arco_channel",
            "severity": "critical",
            "message": "Sin canal ARCO oficial, el responsable puede alegar falta de recepcion por el area competente.",
        })

    if not _present(responsable.get("domicilio")):
        risks.append({
            "code": "missing_legal_address",
            "severity": "medium",
            "message": "El domicilio fortalece identificacion del responsable y permite contrastar aviso de privacidad.",
        })

    description = str(rel.get("descripcion", "")).lower()
    if any(word in description for word in ["sucursal", "tienda", "modulo", "kiosco"]) and not _present(rel.get("folio_contrato_linea_o_cuenta")):
        risks.append({
            "code": "branch_scope_defense",
            "severity": "high",
            "message": "Si el hecho ocurrio en sucursal, identifica que la solicitud se dirige al responsable legal completo y agrega cuenta/linea/folio para evitar que acoten indebidamente el alcance.",
        })

    if not _present(rel.get("descripcion")):
        missing.append("relacion_juridica.descripcion")
        risks.append({
            "code": "weak_legal_relationship",
            "severity": "high",
            "message": "Sin relacion juridica o contexto, el responsable puede alegar imposibilidad de localizar datos o tratamiento necesario no delimitado.",
        })

    return {
        "ok": not any(r["severity"] == "critical" for r in risks),
        "missing": missing,
        "checks": checks,
        "risks": risks,
        "recommendation": "Usar exclusivamente datos del aviso de privacidad vigente y dirigir la solicitud al responsable legal, no a la sucursal ni al nombre comercial.",
    }


def validate_arco_case(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Full intake audit before drafting."""
    case = _as_dict(case_data)
    missing: list[str] = []
    warnings: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []

    required_paths = [
        "titular.nombre_completo",
        "titular.identificacion.tipo",
        "titular.identificacion.vigente",
        "titular.identificacion.se_adjunta_copia",
        "solicitud.ciudad",
        "solicitud.fecha",
        "medio_notificaciones.valor",
        "responsable.naturaleza",
        "responsable.nombre_legal",
        "responsable.domicilio",
        "responsable.canal_arco",
        "responsable.fuente_aviso_privacidad",
        "responsable.fuente_aviso_privacidad.tipo",
        "responsable.fuente_aviso_privacidad.referencia",
        "responsable.fuente_aviso_privacidad.fecha_consulta",
        "responsable.fuente_aviso_privacidad.es_fuente_oficial",
        "relacion_juridica.descripcion",
        "datos_personales",
        "derechos_solicitados",
    ]

    for path in required_paths:
        if not _present(_get(case, path)):
            missing.append(path)

    placeholder_paths = _find_placeholder_paths(case)
    for path in placeholder_paths:
        if path not in missing:
            missing.append(path)

    if _present(_get(case, "responsable.naturaleza")) and _get(case, "responsable.naturaleza") != "privado":
        raw_val = _get(case, "responsable.naturaleza")
        blockers.append({
            "code": "wrong_legal_regime",
            "message": f"responsable.naturaleza debe ser 'privado'. Recibiste '{raw_val}'. La LFPDPPP solo aplica a sujetos regulados privados (empresas y personas fisicas con actividad empresarial). Si el responsable es autoridad publica, debes usar la ley general de proteccion de datos para sujetos obligados.",
        })

    if _get(case, "titular.identificacion.vigente") is False:
        blockers.append({
            "code": "expired_id",
            "message": "La identificacion debe acreditar identidad; si esta vencida, el responsable puede negar por falta de acreditacion.",
        })
    if _get(case, "titular.identificacion.se_adjunta_copia") is False:
        blockers.append({
            "code": "identity_not_attached",
            "message": "El articulo 28 fraccion II exige documentos que acrediten identidad.",
        })

    if _get(case, "solicitud.etapa") == "escalamiento_secretaria" and not _present(_get(case, "prueba_envio.acuse_o_folio")):
        blockers.append({
            "code": "missing_receipt_for_secretaria",
            "message": "Para solicitud de proteccion ante Secretaria debe acompanarse constancia que pruebe fecha de presentacion ante el responsable conforme al articulo 40.",
        })
    elif not _present(_get(case, "prueba_envio.acuse_o_folio")):
        warnings.append({
            "code": "receipt_needed_after_sending",
            "severity": "medium",
            "message": "Antes de escalar, conserva acuse, folio, encabezados de correo o constancia que pruebe fecha de presentacion.",
        })

    names = _right_names(case)
    if not names:
        blockers.append({"code": "no_right_selected", "message": "Debe describirse el derecho ARCO o lo solicitado."})

    unknown = [name for name in names if name not in VALID_RIGHTS]
    for name in unknown:
        blockers.append({
            "code": "unknown_right",
            "message": f"Derecho o peticion no reconocida: {name}.",
        })

    if {"acceso", "rectificacion", "cancelacion", "oposicion"}.issubset(set(names)):
        warnings.append({
            "code": "overbroad_all_arco",
            "severity": "medium",
            "message": "Ejercer todos los ARCO puede ser valido, pero si no esta justificado puede parecer generico y facilitar respuestas parciales.",
        })

    data_items = case.get("datos_personales")
    if not isinstance(data_items, list):
        missing.append("datos_personales")
        blockers.append({
            "code": "invalid_data_personales_format",
            "message": "datos_personales debe ser una lista (array) de objetos con descripcion, categoria y sensible.",
        })
    elif not data_items:
        missing.append("datos_personales")
    else:
        for index, item in enumerate(data_items):
            if not isinstance(item, dict):
                blockers.append({
                    "code": "invalid_data_item",
                    "message": f"datos_personales[{index}] debe ser objeto con descripcion, categoria y sensible.",
                })
                continue
            for field in ("descripcion", "categoria", "sensible"):
                if field not in item or not _present(item.get(field)):
                    missing.append(f"datos_personales[{index}].{field}")
            if _data_item_requires_sensitive(item) and item.get("sensible") is not True:
                blockers.append({
                    "code": "data_requires_sensitive_treatment",
                    "message": f"datos_personales[{index}] contiene categoria o descripcion que exige tratamiento sensible conforme al articulo 8; debe marcarse sensible=true o justificarse fuera del MCP.",
                })
            if str(item.get("categoria", "")).strip().lower() in CONTEXTUAL_HIGH_RISK_CATEGORIES and item.get("sensible") is not True:
                warnings.append({
                    "code": "contextual_high_risk_data",
                    "severity": "medium",
                    "message": f"datos_personales[{index}] no siempre es sensible por categoria, pero puede requerir analisis reforzado segun contexto, volumen, finalidad y riesgo.",
                })

    for right_idx, right in enumerate(_rights(case)):
        if not isinstance(right, dict):
            continue
        name = str(right.get("tipo", "")).strip().lower()
        if name not in VALID_RIGHTS:
            continue
        rule = RIGHTS[name]
        if not _present(right.get("peticion_concreta")):
            missing.append(f"derechos_solicitados[{right_idx}].peticion_concreta")
        if rule.get("requires_data_description") and not _present(case.get("datos_personales")):
            blockers.append({
                "code": "missing_data_description",
                "message": f"{name} exige describir claramente los datos personales involucrados, salvo acceso puro.",
            })
        if name == "oposicion" and right.get("supuesto_oposicion") == "tratamiento_automatizado":
            for field in (
                "descripcion_tratamiento_automatizado",
                "efecto_juridico_o_afectacion_significativa",
                "aspectos_personales_evaluados",
            ):
                if not _present(right.get(field)):
                    blockers.append({
                        "code": f"missing_{field}",
                        "message": f"Para oposicion por tratamiento automatizado falta {field}.",
                    })
        else:
            for field in rule.get("critical_fields", []):
                if not _present(right.get(field)):
                    blockers.append({
                        "code": f"missing_{field}",
                        "message": f"Para {name} falta {field}.",
                    })
        if name == "cancelacion":
            warnings.append({
                "code": "cancellation_exceptions",
                "severity": "high",
                "message": "La cancelacion debe formularse considerando bloqueo y excepciones del articulo 25; no pedir borrado absoluto inmediato.",
            })
        if name == "oposicion":
            warnings.append({
                "code": "opposition_legal_obligation_limit",
                "severity": "high",
                "message": "La oposicion no procede si el tratamiento es necesario para una obligacion legal; delimita finalidades secundarias o tratamientos excesivos.",
            })
            if right.get("supuesto_oposicion") != "tratamiento_automatizado" and _damage_statement_is_weak(right.get("dano_o_perjuicio_oposicion")):
                blockers.append({
                    "code": "weak_opposition_damage_statement",
                    "message": "Para oposicion por causa legitima, el dano o perjuicio debe ser concreto, especifico y no una formula generica.",
                })
        if name == "limitacion_uso_divulgacion":
            warnings.append({
                "code": "not_autonomous_arco",
                "severity": "medium",
                "message": "Limitacion de uso/divulgacion es complemento, no derecho ARCO autonomo.",
            })

    identity = audit_responsable_identity(case)
    for risk in identity["risks"]:
        if risk["severity"] == "critical":
            blockers.append({"code": risk["code"], "message": risk["message"]})
        else:
            warnings.append(risk)

    source_audit = audit_source_provenance(case)
    for blocker in source_audit["blockers"]:
        blockers.append({"code": blocker["code"], "message": blocker["message"]})
    warnings.extend(source_audit["warnings"])

    basis = select_legal_basis(case)
    ready = not missing and not blockers

    return {
        "ok": True,
        "ready_to_draft": ready,
        "summary": asdict(CaseSummary.from_validation({
            "ready_to_draft": ready,
            "blockers": blockers,
            "warnings": warnings,
            "missing": _dedupe(missing),
        })),
        "missing": _dedupe(missing),
        "missing_rationale": {path: _REQUIRED_BY.get(path, "requerido por las reglas de validacion del caso")
                              for path in _dedupe(missing)},
        "blockers": blockers,
        "blocker_rationale": {b["code"]: _BLOCKER_RATIONALE.get(b["code"], "requerido por las reglas de validacion del caso")
                              for b in blockers if isinstance(b, dict) and "code" in b},
        "warnings": warnings,
        "identity_audit": identity,
        "source_audit": source_audit,
        "legal_basis": basis,
        "rejection_vectors_checked": [
            "wrong legal entity",
            "trade name only",
            "branch/sucursal scope defense",
            "wrong ARCO channel",
            "unofficial or stale privacy notice",
            "third-party source used as privacy notice",
            "identity not accredited",
            "representative not accredited",
            "vague data description",
            "wrong right selected",
            "opposition without cause",
            "cancellation ignoring legal exceptions",
            "rectification without evidence",
            "sanctions overstated",
            "wrong authority",
        ],
        "legal_framework_note": "Validacion realizada contra la LFPDPPP del decreto del 20 de marzo de 2025 (ley vigente). La ley de 2010 fue abrogada. Autoridad: Secretaria Anticorrupcion y Buen Gobierno.",
    }


def _format_articles(ids: list[str]) -> str:
    return ", ".join(sorted(ids, key=int))


def _data_list(case: dict[str, Any]) -> str:
    data_items = case.get("datos_personales", [])
    if not isinstance(data_items, list):
        return "- [datos personales no estructurados]"
    lines = []
    for item in data_items:
        if isinstance(item, dict):
            marker = " (sensible)" if item.get("sensible") else ""
            lines.append(f"- {item.get('descripcion', '[dato]')}{marker}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines) if lines else "- [datos personales]"


NUMEROS_CLAUSULA = {
    1: "PRIMERO", 2: "SEGUNDO", 3: "TERCERO", 4: "CUARTO",
    5: "QUINTO", 6: "SEXTO", 7: "SEPTIMO", 8: "OCTAVO",
    9: "NOVENO", 10: "DECIMO",
}


def _build_clause_heading(num: int, article_label: str, suffix: str = "") -> str:
    """Articulo X, fraccion II: PRIMERO. Con fundamento en el articulo..."""
    base = f"articulo {article_label}"
    if suffix:
        base += f", {suffix}"
    label = NUMEROS_CLAUSULA.get(num, str(num))
    return f"{label}. Con fundamento en el {base} de la Ley, "


def draft_arco_request(case_data: dict[str, Any] | str, force: bool = False, validation: dict[str, Any] | None = None, preview: bool = False) -> dict[str, Any]:
    """Draft a legally guarded ARCO request if the intake is complete.

    If preview=True, generates a draft with visible [FALTA: ...] markers
    for missing fields, allowing the LLM to iterate on the case.
    """
    case = _as_dict(case_data)
    if validation is None:
        validation = validate_arco_case(case)
    is_ready = validation["ready_to_draft"]

    if not is_ready and not preview:
        return {
            "ok": False,
            "error_type": "intake_not_ready",
            "message": "No se redacta version final porque hay faltantes o bloqueadores criticos. Usa preview=True para ver un borrador con marcadores de campos faltantes.",
            "validation": validation,
        }

    # En modo preview, usar marcadores [FALTA: ...] en vez de placeholders genéricos
    def _val(path: str, fallback: str) -> str:
        raw = _get(case, path)
        if preview and not _present(raw):
            return f"[FALTA: {path}]"
        return raw if _present(raw) else fallback

    titular = _val("titular.nombre_completo", "[NOMBRE DEL TITULAR]")
    ciudad = _val("solicitud.ciudad", "[CIUDAD]")
    fecha = _val("solicitud.fecha", "[FECHA]")
    medio = _val("medio_notificaciones.valor", "[MEDIO DE NOTIFICACIONES]")
    responsable = _val("responsable.nombre_legal", "[RESPONSABLE LEGAL]")
    canal = _val("responsable.canal_arco", "[CANAL ARCO]")
    aviso_ref = _val("responsable.fuente_aviso_privacidad.referencia", "[FUENTE DEL AVISO]")
    aviso_fecha = _val("responsable.fuente_aviso_privacidad.fecha_consulta", "[FECHA DE CONSULTA]")
    relacion = _val("relacion_juridica.descripcion", "[RELACION JURIDICA]")
    folio = _get(case, "relacion_juridica.folio_contrato_linea_o_cuenta", "")
    id_tipo = _val("titular.identificacion.tipo", "[IDENTIFICACION]")

    excluded_from_request_basis = set(SECRETARIA_ARTICLES + SANCTION_ARTICLES + PENAL_ARTICLES)
    basis_ids = [
        article_id
        for article_id in validation["legal_basis"]["selected_articles"]
        if article_id not in excluded_from_request_basis
    ]
    reserve_ids = [
        article_id
        for article_id in validation["legal_basis"]["selected_articles"]
        if article_id in excluded_from_request_basis
    ]
    right_sections: list[str] = []

    for right in _rights(case):
        if not isinstance(right, dict):
            continue
        name = str(right.get("tipo", "")).strip().lower()
        if name not in VALID_RIGHTS:
            continue
        petition = right.get("peticion_concreta") or "[peticion concreta]"
        num = len(right_sections) + 1
        if name == "oposicion":
            if right.get("supuesto_oposicion") == "tratamiento_automatizado":
                right_sections.append(
                    _build_clause_heading(num, "26", "fraccion II")
                    + f"solicito el cese u oposicion respecto de {petition}. "
                    f"El tratamiento automatizado identificado consiste en: {right.get('descripcion_tratamiento_automatizado', '[tratamiento automatizado]')}. "
                    f"El efecto juridico no deseado o afectacion significativa es: {right.get('efecto_juridico_o_afectacion_significativa', '[efecto o afectacion]')}. "
                    f"Los aspectos personales evaluados o inferidos son: {right.get('aspectos_personales_evaluados', '[aspectos evaluados]')}. "
                    "Solicito que se indique si existe intervencion humana significativa, la logica general aplicada y la base juridica concreta del tratamiento."
                )
            else:
                right_sections.append(
                    _build_clause_heading(num, "26", "fraccion I")
                    + f"solicito el cese del tratamiento consistente en {petition}. "
                    f"La causa legitima es: {right.get('causa_legitima_oposicion', '[causa legitima]')}. "
                    f"Mi situacion especifica es: {right.get('situacion_especifica_oposicion', '[situacion especifica]')}. "
                    f"La persistencia del tratamiento puede causarme: {right.get('dano_o_perjuicio_oposicion', '[dano o perjuicio]')}. "
                    "Si consideran que el tratamiento es necesario para cumplir una obligacion legal, solicito identificar la obligacion concreta, su fuente normativa, el dato indispensable y la finalidad estrictamente necesaria."
                )
        elif name == "cancelacion":
            right_sections.append(
                _build_clause_heading(num, "24")
                + f"solicito la cancelacion de {petition}, con el bloqueo previo que legalmente corresponda y la supresion posterior al concluir el plazo aplicable. "
                "Si estiman actualizada alguna excepcion del articulo 25, solicito identificar la fraccion aplicable, el dato afectado, la finalidad que justifica su conservacion y las pruebas pertinentes."
            )
        elif name == "rectificacion":
            right_sections.append(
                _build_clause_heading(num, "23")
                + f"solicito rectificar {right.get('dato_actual_rectificacion', '[dato actual]')} para que conste como {right.get('dato_correcto_rectificacion', '[dato correcto]')}. "
                f"Anexo como soporte: {right.get('documento_soporte_rectificacion', '[documento soporte]')}."
            )
        elif name == "acceso":
            right_sections.append(
                _build_clause_heading(num, "22")
                + f"solicito {petition}. Esto incluye confirmacion de tratamiento, copia o puesta a disposicion de mis datos personales, finalidades, categorias de datos, origen cuando no provengan directamente de mi, transferencias ya realizadas o previstas, terceros receptores o categorias de receptores y plazo o criterio de conservacion."
            )
        elif name == "limitacion_uso_divulgacion":
            right_sections.append(
                _build_clause_heading(num, "11, 15 fraccion IV, 35 y 36")
                + f"solicito limitar el uso y divulgacion de mis datos para {petition}. "
                "Esta peticion se formula respecto de finalidades secundarias, mercadotecnia, publicidad, prospeccion comercial, perfilamiento no necesario y transferencias futuras o no indispensables."
            )
        elif name == "revocacion_consentimiento":
            right_sections.append(
                _build_clause_heading(num, "7")
                + f"solicito revocar mi consentimiento respecto de {petition}, sin efectos retroactivos y sin afectar tratamientos estrictamente necesarios por ley o por la relacion juridica aplicable."
            )

    folio_text = f" Referencia de localizacion: {folio}." if folio else ""
    rfc = _get(case, "responsable.rfc", "")
    domicilio = _get(case, "responsable.domicilio", "")
    rfc_line = f"R.F.C.: {rfc}\n" if rfc else ""
    domicilio_line = f"{domicilio}\n" if domicilio else ""
    right_sections_text = chr(10).join(right_sections)
    draft = f"""ASUNTO: Ejercicio de Derechos ARCO ({", ".join(_right_display_names(case))}).

{ciudad}, {fecha}

A LA ATENCION DEL DEPARTAMENTO DE DATOS PERSONALES DE
{responsable}
{rfc_line}{domicilio_line}
PRESENTE.

Quien suscribe, {titular}, por mi propio derecho, en mi caracter de titular de los datos personales que mas adelante se detallan, senalando para oir y recibir notificaciones {medio}, comparezco formalmente con fundamento en los articulos {_format_articles(basis_ids)} de la Ley Federal de Proteccion de Datos Personales en Posesion de los Particulares (en lo sucesivo, la Ley), para ejercer de manera expresa mis derechos ARCO bajo los siguientes terminos:

La presente solicitud se formula ante el responsable legal identificado en su aviso de privacidad vigente, no ante una sucursal, modulo, punto de venta o area operativa aislada. En caso de que un area interna distinta conserve o trate los datos, solicito que esta peticion sea canalizada internamente al departamento competente sin restringir indebidamente el alcance de la solicitud.

Mantengo o mantuve relacion con {responsable} consistente en: {relacion}.{folio_text} Para evitar cualquier ambiguedad, hago constar que la identidad, domicilio y canal de atencion se tomaron del aviso de privacidad consultado en {aviso_ref} el {aviso_fecha}. Si el responsable no ha designado persona o departamento de datos personales, solicito que esta comunicacion sea turnada al area competente y que se me informe el dato de contacto designado para el tramite, conforme al articulo 29 de la Ley.

Acredito mi identidad con copia de {id_tipo}, que se acompana como anexo, conforme al articulo 28, fraccion II, de la Ley. Los datos personales involucrados en la presente solicitud son los siguientes:

{_data_list(case)}

En virtud de lo anterior, formulo las siguientes peticiones:

{right_sections_text}

Solicito que se acuse recibo de la presente por el mismo medio de envio o por el medio senalado para notificaciones, indicando fecha de recepcion, hora, folio si existe y area o persona que la recibe. Hago valer que el ejercicio de los derechos ARCO es gratuito conforme al articulo 34 de la Ley, sin perjuicio de costos estrictamente limitados a reproduccion, copias o envio cuando legalmente procedan y se justifiquen.

Toda negativa total o parcial debera comunicarse dentro del plazo legal, por el mismo medio senalado para notificaciones, expresando de forma fundada y motivada la causa especifica de improcedencia prevista en el articulo 33 de la Ley y acompanando, en su caso, las pruebas pertinentes que sustenten dicha determinacion.

Conforme al articulo 31 de la Ley, el responsable cuenta con un plazo de veinte dias habiles contado desde la recepcion de esta solicitud para comunicar la determinacion adoptada. Dicho plazo podra ampliarse por una unica vez y por un periodo igual, siempre que exista justificacion para ello y sea notificado dentro del plazo original. De resultar procedente, la determinacion debera hacerse efectiva dentro de los quince dias habiles siguientes a su comunicacion.

En caso de falta de respuesta, respuesta incompleta, negativa injustificada, entrega en formato incomprensible o cumplimiento defectuoso, me reservo el derecho de presentar solicitud de proteccion de datos ante la {AUTHORITY}, en terminos de los articulos 40 y 41 de la Ley, asi como de solicitar la verificacion que corresponda conforme al articulo 54 de la Ley y de acudir al juicio de amparo contra resoluciones de la Secretaria en terminos del articulo 51 de la Ley, sin perjuicio de los derechos indemnizatorios previstos en el articulo 53 de la Ley cuando procedan.

Se hace constar que las conductas de incumplimiento, negligencia, dolo, tratamiento contrario a los principios de la Ley, transferencia indebida, uso ilegitimo, obstruccion de verificacion o afectacion al ejercicio de derechos ARCO pueden actualizar infracciones previstas en el articulo 58 de la Ley, sancionables conforme al articulo 59 de la Ley, segun la conducta especifica que en su caso se acredite mediante el procedimiento correspondiente.

Anexos:

{_format_anexos(case)}

ATENTAMENTE

(Firma)

{titular}
"""


    return {
        "ok": True,
        "draft": draft,
        "is_preview": preview,
        "validation": validation,
        "selected_articles": validation["legal_basis"]["selected_articles"],
        "request_basis_articles": basis_ids,
        "reserve_articles": reserve_ids,
    }


def _format_anexos(case: dict[str, Any]) -> str:
    anexos = case.get("anexos", [])
    if not isinstance(anexos, list) or not anexos:
        return "1. Copia de identificacion oficial vigente."
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(anexos, start=1))


def audit_existing_draft(draft_text: str, case_data: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Audit an already drafted request for legally risky wording."""
    case = _as_dict(case_data) if case_data else {}
    text = draft_text or ""
    lower = text.lower()
    findings: list[dict[str, str]] = []

    patterns = [
        (r"\[[^\]]+\]|\brazon social exacta\b|\bcanal arco exacto\b|\bnombre completo del titular\b|\bdomicilio exacto\b|\blinea/cuenta/folio\b", "unresolved_placeholder", "high", "El borrador conserva placeholders o datos no verificados; no debe enviarse."),
        (r"\binai\b|instituto nacional de transparencia|instituto nacional de transparencia,\s*acceso a la informaci[oó]n", "wrong_authority", "high", "Evita citar al INAI o su nombre completo como autoridad actual para particulares bajo el decreto 2025."),
        (r"\bifai\b|\bprodato?s\b|\bifai-prodatos\b", "obsolete_procedure_or_authority", "high", "IFAI/PRODATOS no debe presentarse como via vigente de proteccion bajo el decreto 2025."),
        (r"ley (federal de protecci[oó]n de datos personales )?(publicada|vigente|expedida).*2010|ley de 2010 vigente", "obsolete_law_version", "high", "No presentes la ley de 2010 como version vigente; usa el decreto del 20 de marzo de 2025."),
        (r"art[ií]culo 22.{0,80}derechos arco|derechos arco.{0,80}art[ií]culo 22", "old_article_mapping", "medium", "Bajo la matriz de este decreto, el articulo 21 habilita ARCO y el 22 corresponde a acceso; revisa la cita.",
        ),
        (r"\brgpd\b|\bgdpr\b|reglamento general de protecci[oó]n de datos", "wrong_foreign_regime", "high", "No uses RGPD/GDPR como fundamento de una solicitud bajo la LFPDPPP mexicana salvo analisis transfronterizo separado."),
        (r"derecho al olvido|habeas data|derecho de portabilidad|portabilidad de datos", "foreign_regime_concept", "medium", "Evita importar categorias de otros regimenes; formula la peticion como ARCO, revocacion o limitacion segun la LFPDPPP."),
        (r"multa automatica|autom[aá]ticamente.*multa|(?:160,?000|320,?000).{0,30}(?:uma|unidad)", "sanction_overstatement", "high", "No menciones montos especificos de UMA (160,000 o 320,000) como amenaza. Las sanciones del articulo 59 dependen de infraccion concreta y procedimiento; no son automaticas."),
        (r"\bimprorrogable\b", "wrong_deadline_type", "high", "El plazo de 20 dias NO es improrrogable. El articulo 31 permite ampliacion UNICA por periodo igual, con justificacion."),
        (r"d[ií]as naturales", "wrong_deadline_unit", "high", "La Ley define dias como dias habiles."),
        (r"borrad[oa] inmediato|eliminaci[oó]n inmediata", "cancellation_overstatement", "medium", "Cancelacion implica bloqueo previo y supresion posterior, con excepciones."),
        (r"quinto derecho arco|derecho arco de limitaci[oó]n|derechos arco.{0,30}limitaci[oó]n", "wrong_right_taxonomy", "medium", "Limitacion de uso/divulgacion no es derecho ARCO autonomo. No la presentes junto a 'derechos ARCO' como si fuera uno de ellos."),
        (r"transparencia para el pueblo", "wrong_private_authority", "medium", "Para particulares, la Ley define Secretaria como Secretaria Anticorrupcion y Buen Gobierno."),
        (r"autoridad garante", "ambiguous_authority_label", "medium", "Para la LFPDPPP de particulares usa Secretaria Anticorrupcion y Buen Gobierno; evita usar 'autoridad garante' como sustituto del nombre oficial."),
        (r"\bdenunci[aeoáé]r?\b", "imprecise_procedural_term", "medium", "Para escalar el asunto usa 'solicitud de proteccion de datos' o 'procedimiento de proteccion de derechos', no 'denunciar'/'denuncia' salvo contexto penal especifico (arts. 62-64 LFPDPPP)."),
        # Amparo-specific patterns (Ley de Amparo 2013)
        (r"amparo directo.{0,50}secretar[ií]a", "wrong_amparo_type", "high", "Contra resoluciones de la Secretaria procede amparo indirecto (art. 107 LA), no directo."),
        (r"(?:30|treinta)\s*d[ií]as.{0,100}amparo|amparo.{0,100}(?:30|treinta)\s*d[ií]as", "wrong_amparo_deadline", "high", "El plazo para amparo contra resolucion de la Secretaria es de 15 dias, no 30. Los 30 dias son para normas autoaplicativas (art. 17 LA)."),
        (r"(?=.*amparo)(?=.*tribunal colegiado)", "wrong_amparo_court", "medium", "El amparo indirecto se promueve ante Juzgado de Distrito, no ante Tribunal Colegiado (este conoce de amparo directo)."),
        (r"\bd[ií]as naturales.{0,50}amparo", "wrong_amparo_day_type", "high", "El plazo de amparo se computa en dias habiles conforme al art. 19 LA y al art. 28 LFPA supletoriamente."),
        (r"art[ií]culo 21.{0,50}amparo", "old_amparo_article", "medium", "En la Ley de Amparo de 2013 el plazo ya no esta en el art. 21; esta en el art. 17."),
        # Fracción-citation accuracy patterns
        (r"art[ií]culo 26.{0,30}fracci[oó]n\s+ii\b", "wrong_opposition_fraction", "high", "El articulo 26 fraccion II corresponde a tratamiento AUTOMATIZADO. Si tu oposicion es por causa legitima, cita la fraccion I. Si estas invocando fracc II sin describir un tratamiento automatizado concreto, la cita es juridicamente incorrecta."),
        (r"art[ií]culo 36.{0,20}fracci[oó]n\s+iii.{0,120}oposici[oó]n|oposici[oó]n.{0,120}art[ií]culo 36.{0,20}fracci[oó]n\s+iii", "transfer_exception_vs_opposition", "high", "El articulo 36 fraccion III permite transferencias a empresas del mismo grupo SIN consentimiento. La oposicion del art. 26 y las excepciones del art. 36 son figuras juridicas distintas que operan en planos diferentes. No afirmes que la oposicion 'anula' automaticamente la excepcion del art. 36 sin un analisis juridico especifico."),
        (r"fundamento en los art[ií]culos.{0,200}oposici[oó]n.{0,10}y.{0,10}limitaci[oó]n(?!.{0,30}complementaria)", "mixed_opposition_limitation", "medium", "La oposicion (art. 26) y la limitacion de uso/divulgacion (arts. 11, 15, 35, 36) son figuras juridicas distintas con fundamentos diferentes. No las trates como un solo instrumento ni las fundamente con los mismos articulos."),
    ]

    for pattern, code, severity, message in patterns:
        if re.search(pattern, lower, re.DOTALL):
            findings.append({"code": code, "severity": severity, "message": message})

    # Suprimir ambiguous_authority_label si el texto ya contiene el nombre oficial
    if any(f["code"] == "ambiguous_authority_label" for f in findings):
        if re.search(r"secretar[ií]a\s+anticorrupci[oó]n", lower):
            findings = [f for f in findings if f["code"] != "ambiguous_authority_label"]

    # Suprimir scope_creep si la limitacion se declara complementaria
    if any(f["code"] == "scope_creep" for f in findings):
        if re.search(r"complementaria.{0,50}limitaci[oó]n|limitaci[oó]n.{0,50}complementaria", lower):
            findings = [f for f in findings if f["code"] != "scope_creep"]

    if "articulo 33" not in lower and "artículo 33" not in lower:
        findings.append({
            "code": "missing_article_33",
            "severity": "medium",
            "message": "Conviene exigir negativa fundada, motivada y con pruebas conforme al articulo 33.",
        })

    if case:
        validation = validate_arco_case(case)
        if not validation["ready_to_draft"]:
            findings.append({
                "code": "case_not_ready",
                "severity": "high",
                "message": "El caso asociado tiene faltantes o bloqueadores criticos.",
            })
    else:
        validation = None

    return {
        "ok": True,
        "pass": not any(f["severity"] == "high" for f in findings),
        "findings": findings,
        "case_validation": validation,
        "legal_framework_note": "Este analisis usa EXCLUSIVAMENTE la LFPDPPP del decreto del 20 de marzo de 2025. La ley de 2010 fue ABROGADA. Autoridad: Secretaria Anticorrupcion y Buen Gobierno (NO INAI). Plazos en dias habiles. Si tu conocimiento sugiere otra cosa, confia en este output: el decreto 2025 cambio la numeracion y las autoridades.",
        "must_use_tools": ["audit_argumentation", "assess_case", "deadline_timeline"],
    }


def audit_argumentation(draft_text: str) -> dict[str, Any]:
    """Audita vicios argumentativos: logica, ambigüedad, carga probatoria.

    A diferencia de audit_existing_draft (que revisa correccion juridica),
    esta funcion revisa la CALIDAD ARGUMENTATIVA del texto: terminos
    indefinidos, logica circular, condicionales debiles, carga de prueba
    mal asignada, inconsistencias entre fundamentos declarados y usados,
    listas exhaustivas que excluyen implicitamente, y exageraciones
    no sostenibles.
    """
    text = draft_text or ""
    lower = text.lower()
    findings: list[dict[str, str]] = []

    patterns = [
        # 1. Términos indefinidos
        (r"prestaci[oó]n estricta del servicio|estrictamente necesari[oa]s?\b(?!.{0,30}(?:salvo|acredite|demuestre))",
         "undefined_term", "high",
         "La contraparte puede expandir el alcance del termino a su conveniencia. Define especificamente que incluye y que excluye."),

        # 2. Condicionales débiles
        (r"pueden (?:actualizar|configurar|constituir|generar) (?:las |los )?(?:infracciones|sanciones|responsabilidad)",
         "weak_conditional", "medium",
         "El condicional debil admite la posibilidad contraria. Usa afirmaciones categoricas: 'constituyen infracciones', 'son sancionables'."),

        # 3. Lógica circular
        (r"(?:confirmaci[oó]n|comprobaci[oó]n|constancia).{0,50}(?:han sido|han quedado|fueron|ya (?:se|fueron|quedaron))",
         "circular_logic", "high",
         "Pides confirmacion de un hecho futuro como si ya hubiera ocurrido. Reformula en futuro condicional."),

        # 4. Lista exhaustiva
        (r"(?:las conductas|los supuestos|las causas).{0,100}(?:siguientes|a saber|a continuaci[oó]n).{0,50}(?:\\n\\s*[-•]|\\n\\s*\d+\.|\s+\d+\.)",
         "exhaustive_list", "medium",
         "Una lista exhaustiva excluye implicitamente lo no listado. Usa lenguaje generico: 'el incumplimiento de las obligaciones previstas en la Ley, incluyendo...'."),

        # 5. Exageración
        (r"irreversible|irreparable|catastr[oó]fic[oa]|devastador[a]|grav[ií]sim[oa]|absolut[oa]",
         "unsustainable_exaggeration", "medium",
         "La exageracion debilita el argumento. Usa terminos medibles: 'riesgo concreto', 'afectacion'."),

        # 6. Vacío referencial
        (r"plazo legal\b(?!.{0,50}(?:art[ií]culo\s*\d+|previsto|establecido|se[ñn]alado))",
         "reference_gap", "medium",
         "El termino carece de referencia precisa. Especifica el plazo: 'el plazo de veinte dias habiles previsto en el articulo 31 de la Ley'."),

        # 7. Carga de prueba mal asignada
        (r"(?:salvo\\s+que|cuando|a\\s+menos\\s+que)(?:.|\\n){0,50}(?:no\\s+)?sean?\\s+(?:estrictamente\\s+)?necesari[oa]s?",
         "misplaced_burden_of_proof", "high",
         "El titular asume la carga de demostrar innecesariedad. Invierte la formula: 'salvo que el responsable acredite que son necesarias'."),

        # 8. Falacia de causa falsa
        (r"(?:la culpa|el responsable|la causa|el motivo)\s+(?:de|por)\s+(?:el|la|que)\s.{0,80}(?:\bes\b|\bfue\b|\bson\b|\bfueron\b)",
         "false_causality", "medium",
         "Atribuyes causalidad donde solo hay correlacion o sucesion temporal."),

        # 9. Ignoratio elenchi
        (r"(?:todo el mundo|todas las personas|cualquier titular).{0,100}(?:por lo tanto|en consecuencia|solicito|exijo)",
         "ignoratio_elenchi", "medium",
         "Argumentas sobre un principio general para concluir sobre un caso especifico sin conectar ambos."),

        # 10. Apelación a autoridad no vinculante
        (r"(?:doctrina|tratadista|derecho\s+(?:comparado|europeo|anglosaj)|rgpd|gdpr|convenio\s+(?:europeo|internacional))",
         "appeal_to_nonbinding_authority", "medium",
         "Citas doctrina o derecho extranjero como si tuviera fuerza normativa en Mexico."),

        # 11. Pregunta compleja
        (r"(?:por\s+qu[eé]\s+(?:siguen|contin[uú]an|insisten).{0,40}tratando|\\u00bfpor\s+qu[eé].{0,40}\\?)",
         "loaded_presupposition", "medium",
         "Tu afirmacion contiene una presuposicion no probada. Afirma solo hechos verificables."),

        # 12. Sobregeneralización
        (r"(?:todo|toda|todos|todas|cualquier|siempre|nunca|jam[aá]s|absolutamente)\s.{0,100}(?:dato|tratamiento|transferencia|derecho)",
         "overgeneralization", "medium",
         "Aplicas una regla general a un caso que puede tener excepciones legales (arts. 9, 25, 36)."),

        # 13. Auto-contradicción
        (r"(?:cese\s+definitivo|oposici[oó]n\s+total|opongo\s+(?:de\s+manera\s+)?total|cancelaci[oó]n\s+absoluta|definitiva\s+y\s+total|total\s+y\s+definitiva).{0,300}(?:salvo\s+que|a\s+menos\s+que|excepto|con\s+excepci[oó]n)",
         "self_contradiction", "high",
         "Una seccion usa lenguaje absoluto mientras otra introduce condiciones. Unifica el criterio."),

        # 14. Scope creep
        (r"(?:oposici[oó]n|opongo).{0,300}limitaci[oó]n.{0,200}(?:transfer|ceder|compartir)",
         "scope_creep", "medium",
         "La oposicion (art. 26) ya cubre transferencias porque 'tratamiento' las incluye (art. 2). Pedirlo bajo limitacion debilita la oposicion."),

        # 15. Placeholder
        (r"", "ambiguous_subject", "medium", ""),
    ]

    for pattern, code, severity, message in patterns:
        if not pattern:
            continue
        if re.search(pattern, lower, re.DOTALL):
            findings.append({"code": code, "severity": severity, "message": message})

    # Supresión: scope_creep si la limitación es complementaria
    if any(f["code"] == "scope_creep" for f in findings):
        if re.search(r"complementaria.{0,50}limitaci[oó]n|limitaci[oó]n.{0,50}complementaria", lower, re.DOTALL):
            findings = [f for f in findings if f["code"] != "scope_creep"]

    # Fundamento inconsistente
    header_match = re.search(r"con fundamento en los art[ií]culos\s+(.+?)(?:de la ley|del ordenamiento)", lower, re.DOTALL)
    if header_match:
        header_arts = set(re.findall(r"(\d+)", header_match.group(1)))
        body_arts = set(re.findall(r"art[ií]culo\s+(\d+)", lower))
        procedural = {"31","33","40","41","42","43","44","45","46","47","49","50","51","53","54","56","57","58","59","60","61"}
        substantive_orphans = (body_arts - header_arts) - procedural
        if substantive_orphans:
            findings.append({
                "code": "foundation_inconsistency",
                "severity": "high",
                "message": f"El cuerpo cita articulos ({', '.join(sorted(substantive_orphans, key=int))}) no declarados en el fundamento del encabezado. Agregalos al parrafo inicial.",
            })

    return {
        "ok": True,
        "pass": not any(f["severity"] == "high" for f in findings),
        "findings": findings,
        "note": "Este analisis revisa VICIOS ARGUMENTATIVOS (logica, ambiguedad, carga probatoria). Para errores juridicos usa audit_draft.",
        "must_use_tools": ["assess_case", "deadline_timeline", "escalation_basis"],
    }


def add_business_days(start_date: str, business_days: int, holidays: list[str] | None = None) -> str:
    start = _dt.date.fromisoformat(start_date)
    holiday_set = {_dt.date.fromisoformat(h) for h in (holidays or [])}
    current = start
    added = 0
    max_iterations = max(business_days * 10, 1000)
    iterations = 0
    while added < business_days:
        iterations += 1
        if iterations > max_iterations:
            raise ValueError(
                f"No se pudo completar el calculo de {business_days} dias habiles "
                f"desde {start_date}: demasiados dias inhabiles (max {max_iterations} iteraciones)."
            )
        current += _dt.timedelta(days=1)
        if current.weekday() >= 5 or current in holiday_set:
            continue
        added += 1
    return current.isoformat()


def build_timeline(
    fecha_recepcion: str,
    fecha_respuesta: str | None = None,
    holidays: list[str] | None = None,
    fecha_presentacion_secretaria: str | None = None,
    fecha_notificacion_secretaria: str | None = None,
) -> dict[str, Any]:
    """Build ARCO deadline calendar using business days. Holidays are optional."""
    try:
        _dt.date.fromisoformat(fecha_recepcion)
    except (ValueError, TypeError):
        return {"ok": False, "error": f"fecha_recepcion invalida: {fecha_recepcion}. Use formato ISO YYYY-MM-DD."}
    for label, value in [
        ("fecha_respuesta", fecha_respuesta),
        ("fecha_presentacion_secretaria", fecha_presentacion_secretaria),
        ("fecha_notificacion_secretaria", fecha_notificacion_secretaria),
    ]:
        if value is not None:
            try:
                _dt.date.fromisoformat(value)
            except (ValueError, TypeError):
                return {"ok": False, "error": f"{label} invalida: {value}. Use formato ISO YYYY-MM-DD."}
    response_deadline = add_business_days(fecha_recepcion, 20, holidays)
    extended_response_deadline = add_business_days(response_deadline, 20, holidays)
    result: dict[str, Any] = {
        "ok": True,
        "fecha_recepcion": fecha_recepcion,
        "dias_son_habiles": True,
        "limite_respuesta_20_dias_habiles": response_deadline,
        "limite_respuesta_con_ampliacion": extended_response_deadline,
        "note": "Solo se excluyen sabados, domingos y feriados proporcionados en holidays; verifica dias inhabiles oficiales aplicables.",
    }
    if fecha_respuesta:
        result["limite_efectividad_15_dias_habiles"] = add_business_days(fecha_respuesta, 15, holidays)
        result["limite_efectividad_con_ampliacion"] = add_business_days(result["limite_efectividad_15_dias_habiles"], 15, holidays)
        result["limite_prudente_secretaria_15_dias_desde_respuesta"] = add_business_days(fecha_respuesta, 15, holidays)
    else:
        result["puede_acudir_secretaria_desde"] = response_deadline
        result["limite_prudente_secretaria_15_dias_desde_vencimiento"] = add_business_days(response_deadline, 15, holidays)
    if fecha_presentacion_secretaria:
        secretaria_deadline = add_business_days(fecha_presentacion_secretaria, 50, holidays)
        result["fecha_presentacion_secretaria"] = fecha_presentacion_secretaria
        result["limite_resolucion_secretaria_50_dias"] = secretaria_deadline
        result["limite_resolucion_secretaria_con_ampliacion"] = add_business_days(secretaria_deadline, 50, holidays)
        result["limite_cumplimiento_resolucion_favorable_10_dias"] = add_business_days(secretaria_deadline, 10, holidays)
    if fecha_notificacion_secretaria:
        result["fecha_notificacion_secretaria"] = fecha_notificacion_secretaria
        result["limite_presentacion_amparo_15_dias"] = add_business_days(fecha_notificacion_secretaria, 15, holidays)
        result["fundamento_plazo_amparo"] = "Articulo 17 de la Ley de Amparo: el plazo para presentar la demanda de amparo es de quince dias."
        result["amparo_via"] = "Amparo indirecto conforme al articulo 107, fracciones II y III, de la Ley de Amparo en relacion con el articulo 51 de la LFPDPPP."
    return result


def select_escalation_basis(etapa: str = "escalamiento_secretaria") -> dict[str, Any]:
    """Return controlled legal basis for the escalation phase.

    Args:
        etapa: 'escalamiento_secretaria' or 'amparo'.
    """
    result: dict[str, Any] = {
        "ok": True,
        "etapa": etapa,
        "trace": build_trace(),
        "lfpdpPP": {
            "source": DECREE_SOURCE,
            "authority": AUTHORITY,
            "secretaria_articles": SECRETARIA_ARTICLES,
            "sanction_articles": SANCTION_ARTICLES,
        },
    }

    result["lfpa"] = {
        "source": LFPA_SOURCE,
        "role": "Supletoria por articulo 4 de la LFPDPPP.",
        "applicable_articles": {k: LFPA_ARTICLES[k] for k in ["2", "3", "28", "35", "38", "39", "41"]},
    }

    if etapa == "amparo":
        result["amparo"] = {
            "source": AMPARO_SOURCE,
            "role": "Procede contra resoluciones de la Secretaria conforme al articulo 51 de la LFPDPPP.",
            "applicable_articles": AMPARO_ARTICLES,
        }
        result["constitucion"] = {
            "source": CONSTITUTIONAL_SOURCE,
            "role": "Fundamento constitucional directo del derecho a la proteccion de datos y del juicio de amparo.",
            "applicable_articles": CONSTITUTION_ARTICLES,
        }
        result["notes"] = [
            "El amparo procede contra la resolucion definitiva de la Secretaria (amparo indirecto, art. 107 fracs. II y III LA).",
            "El plazo es de 15 dias habiles desde la notificacion de la resolucion (arts. 17 y 19 LA).",
            "Verificar que el caso no incurra en causales de improcedencia del art. 61 LA, en especial la fraccion XX (definitividad): si existe un recurso administrativo que pueda modificar o revocar la resolucion de la Secretaria y suspender sus efectos con alcance similar al amparo, DEBE AGOTARSE antes de promover el amparo.",
            "El principio pro persona (art. 1 constitucional) obliga a interpretar la ley en favor de la maxima proteccion del titular.",
            "La LFPA se aplica supletoriamente en notificaciones, computo de plazos y requisitos formales del acto administrativo.",
            "La suspension del acto reclamado (art. 125 LA) requiere que no haya perjuicio al interes social ni contravencion al orden publico (art. 128 LA).",
        ]
    else:
        result["notes"] = [
            "La LFPA se aplica supletoriamente donde la LFPDPPP guarda silencio (arts. 2, 3, 28, 35, 38, 39, 41 LFPA).",
            "Los requisitos del acto administrativo (art. 3 LFPA) permiten impugnar resoluciones de la Secretaria mal fundadas o motivadas.",
        ]

    return result


def process_case(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Run the full ARCO pipeline in one call: validate → basis → argument_map → draft.

    Returns all intermediate results so the LLM can inspect blockers/missing
    without needing to chain multiple tool calls. If the case is not ready,
    draft will be None and the LLM must resolve missing/blockers first.
    """
    case = _as_dict(case_data)
    validation = validate_arco_case(case)
    basis = select_legal_basis(case)
    argument_map = build_argument_map(case, validation=validation)

    draft_result: dict[str, Any] | None = None
    draft_preview: str | None = None
    if validation["ready_to_draft"]:
        draft_result = draft_arco_request(case, validation=validation)
    else:
        preview = draft_arco_request(case, validation=validation, preview=True)
        draft_preview = preview.get("draft") if preview.get("draft") else None

    result: dict[str, Any] = {
        "ok": True,
        "ready_to_draft": validation["ready_to_draft"],
        "summary": asdict(CaseSummary.from_validation(validation)),
        "trace": build_trace(),
        "validation": {
            "missing": validation["missing"],
            "missing_rationale": validation.get("missing_rationale", {}),
            "blockers": validation["blockers"],
            "blocker_rationale": validation.get("blocker_rationale", {}),
            "warnings": validation["warnings"],
            "ready": validation["ready_to_draft"],
            "total_missing": len(validation["missing"]),
            "total_blockers": len(validation["blockers"]),
            "total_warnings": len(validation["warnings"]),
        },
        "legal_basis": {
            "selected_articles": basis["selected_articles"],
            "request_basis": [a for a in basis["selected_articles"]
                              if a not in set(SECRETARIA_ARTICLES + SANCTION_ARTICLES + PENAL_ARTICLES)],
        },
        "argument_map": argument_map["arguments"],
        "draft": draft_result["draft"] if draft_result else None,
        "draft_preview": draft_preview,
        "next_step": (
            "Caso listo. AHORA DEBES ejecutar TODAS estas herramientas EN ORDEN:\n"
            "  1. audit_draft(draft_text) → detecta errores jurídicos\n"
            "  2. audit_argumentation(draft_text) → detecta vicios lógicos\n"
            "  3. assess_case(case_json) → valora solidez\n"
            "  4. deadline_timeline(fecha) → calcula plazos\n"
            "NO entregues el borrador hasta que audit_draft y audit_argumentation devuelvan pass=true."
            if validation["ready_to_draft"]
            else "Caso no listo. Se genero un draft_preview con marcadores [FALTA: campo]. Completa los campos faltantes y revalida."
        ),
        "must_use_tools": ["audit_draft", "audit_argumentation", "assess_case", "deadline_timeline"] if validation["ready_to_draft"] else [],
    }
    return result


def assess_case(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Emitir una valoracion juridica estructurada del caso ARCO.

    A diferencia de validate_arco_case (que solo lista problemas), esta funcion
    analiza las implicaciones legales de cada hallazgo, asigna un nivel de solidez
    y emite un pronostico sobre la viabilidad del caso si se presentara asi.
    """
    case = _as_dict(case_data)
    validation = validate_arco_case(case)

    blockers = validation.get("blockers", [])
    warnings_list = validation.get("warnings", [])
    missing = validation.get("missing", [])
    blocker_codes = {b["code"] for b in blockers if isinstance(b, dict)}
    identity = validation.get("identity_audit", {})
    source = validation.get("source_audit", {})

    # ── Clasificar severidad ──
    fatal_blockers = blocker_codes & {
        "wrong_legal_regime",
        "wrong_or_unidentified_legal_entity",
        "no_privacy_notice_source",
        "wrong_or_missing_arco_channel",
    }
    legal_blockers = blocker_codes & {
        "data_requires_sensitive_treatment",
        "expired_id", "identity_not_attached",
        "no_right_selected",
        "weak_opposition_damage_statement",
        "missing_data_description",
    }
    source_blockers = blocker_codes & {
        "non_primary_privacy_notice_type",
        "privacy_notice_not_confirmed_official",
        "third_party_source_used_as_notice",
        "official_url_domain_mismatch",
        "placeholder_privacy_notice_reference",
        "stale_privacy_notice_source",
        "missing_receipt_for_secretaria",
        "invalid_privacy_notice_source",
        "invalid_or_missing_consultation_date",
        "future_consultation_date",
        "invalid_official_url",
    }

    # ── Determinar nivel de solidez ──
    if fatal_blockers and not missing:
        nivel = "insostenible"
        descripcion_nivel = (
            "El caso tiene vicios fatales que impiden su tramite. "
            "Si se presenta asi, el responsable puede rechazarlo de plano "
            "por no identificar correctamente al sujeto regulado, "
            "por carecer de fuente de aviso de privacidad verificable "
            "o por no dirigirse al canal ARCO oficial."
        )
    elif fatal_blockers:
        nivel = "incompleto"
        descripcion_nivel = (
            "El caso tiene campos faltantes O valores incorrectos "
            "(ej: naturaleza debe ser 'privado', no 'empresa'). "
            "Completa los campos y corrige los valores segun el schema. "
            "Los bloqueadores actuales probablemente desaparezcan al "
            "completar los datos correctamente."
        )
    elif legal_blockers or source_blockers:
        nivel = "debil"
        descripcion_nivel = (
            "El caso tiene bloqueadores que lo hacen vulnerable a rechazo. "
            "El responsable puede negar fundadamente si los datos sensibles "
            "no estan marcados como tales, si la oposicion carece de dano "
            "concreto, si la fuente del aviso no es oficial o si faltan "
            "elementos probatorios exigidos por la Ley."
        )
    elif missing:
        nivel = "incompleto"
        descripcion_nivel = (
            "Faltan campos requeridos por el articulo 28 de la LFPDPPP. "
            "El responsable puede prevenir al titular o negar la solicitud "
            "por no reunir los requisitos minimos."
        )
    elif len(warnings_list) >= 3:
        nivel = "solido_con_reservas"
        descripcion_nivel = (
            "El caso supera la validacion critica pero acumula advertencias "
            "que un responsable diligente podria explotar para acotar el "
            "alcance de la respuesta o para solicitar aclaraciones."
        )
    elif warnings_list:
        nivel = "solido"
        descripcion_nivel = (
            "El caso supera la validacion con advertencias menores. "
            "Tecnicamente presentable. Las advertencias senalan areas "
            "de mejora que fortalecerian la posicion del titular."
        )
    else:
        nivel = "irrefutable"
        descripcion_nivel = (
            "El caso no tiene bloqueadores, faltantes ni advertencias. "
            "Todos los campos requeridos estan presentes, la fuente del "
            "aviso es oficial y reciente, los datos sensibles estan "
            "correctamente marcados y los derechos ejercidos tienen "
            "causa y peticion concreta."
        )

    # ── Implicaciones por articulo ──
    implicaciones: list[dict[str, str]] = []
    if fatal_blockers:
        implicaciones.append({
            "articulo": "28 LFPDPPP",
            "riesgo": "Rechazo de plano",
            "detalle": "Sin responsable legal identificado desde el aviso de privacidad, la solicitud no cumple los requisitos minimos del art. 28. El responsable puede alegar que nunca recibio una solicitud valida.",
        })
    if legal_blockers:
        implicaciones.append({
            "articulo": "8, 26, 28 LFPDPPP",
            "riesgo": "Negativa fundada",
            "detalle": "El art. 33 permite al responsable negar con causa justificada. Si los datos sensibles no estan marcados o la oposicion carece de dano concreto, el responsable tiene fundamento para una negativa parcial o total.",
        })
    if source_blockers:
        implicaciones.append({
            "articulo": "15 LFPDPPP",
            "riesgo": "Caducidad o desestimacion",
            "detalle": "Si la fuente del aviso no es oficial, esta desactualizada o proviene de terceros, los datos de identidad, domicilio y canal ARCO pueden ser incorrectos. La solicitud podria dirigirse a una entidad inexistente o a un canal no habilitado.",
        })
    if "wrong_deadline_type" in {w.get("code") for w in warnings_list if isinstance(w, dict)}:
        implicaciones.append({
            "articulo": "31 LFPDPPP",
            "riesgo": "Debilitamiento argumental",
            "detalle": "Afirmar que el plazo es 'improrrogable' es juridicamente inexacto. El responsable puede senalar el error y usarlo para cuestionar la seriedad del escrito.",
        })
    if "sanction_overstatement" in {w.get("code") for w in warnings_list if isinstance(w, dict)}:
        implicaciones.append({
            "articulo": "59 LFPDPPP",
            "riesgo": "Perdida de credibilidad",
            "detalle": "Amenazar con montos especificos de sancion debilita la posicion del titular. Las sanciones no son automaticas y dependen de un procedimiento. El responsable puede interpretar esto como desconocimiento de la Ley.",
        })

    # ── Pronostico ──
    if nivel in ("insostenible", "debil"):
        pronostico = (
            "Si este caso se presenta en su estado actual, es altamente "
            "probable que el responsable lo rechace dentro del plazo legal, "
            "ya sea por falta de requisitos formales (art. 28), por "
            "improcedencia de fondo (art. 33) o por dirigirse a una entidad "
            "o canal incorrecto. Se recomienda corregir los bloqueadores "
            "antes de enviar."
        )
    elif nivel == "incompleto":
        pronostico = (
            "Si se presenta incompleto, el responsable puede prevenir al "
            "titular para que subsane en un plazo razonable, o simplemente "
            "negar por no reunir los requisitos. Es preferible completar "
            "los campos faltantes antes del envio."
        )
    elif nivel == "solido_con_reservas":
        pronostico = (
            "El caso es presentable y el responsable esta obligado a "
            "responder en 20 dias habiles. Sin embargo, las advertencias "
            "acumuladas sugieren que la respuesta podria ser parcial o "
            "requerir aclaraciones. Atender las advertencias fortaleceria "
            "la posicion del titular y reduciria el margen de maniobra "
            "del responsable."
        )
    else:
        pronostico = (
            "El caso esta en condiciones optimas para su presentacion. "
            "El responsable tiene la obligacion de responder en 20 dias "
            "habiles (art. 31) y, si la respuesta es negativa, debera "
            "fundarla y motivarla con pruebas (art. 33). De no responder "
            "o de hacerlo deficientemente, el titular puede acudir a la "
            "Secretaria Anticorrupción y Buen Gobierno (art. 40) y, en "
            "ultima instancia, al amparo (art. 51 LFPDPPP, art. 107 LA)."
        )

    return {
        "ok": True,
        "nivel_solidez": nivel,
        "descripcion_nivel": descripcion_nivel,
        "implicaciones_legales": implicaciones,
        "pronostico": pronostico,
        "resumen": {
            "total_bloqueadores": len(blockers),
            "bloqueadores_fatales": len(fatal_blockers),
            "bloqueadores_legales": len(legal_blockers),
            "bloqueadores_fuente": len(source_blockers),
            "total_faltantes": len(missing),
            "total_advertencias": len(warnings_list),
        },
        "trace": build_trace(),
        "must_use_tools": ["audit_draft", "audit_argumentation", "deadline_timeline", "escalation_basis"],
    }


# ── Counter-defenses: tactical playbook against corporate evasion ──

CORPORATE_EVASION_TACTICS: list[dict[str, Any]] = [
    {
        "id": "impose_format",
        "tactica": "Exigir un formato especifico de la empresa como condicion para procesar la solicitud",
        "contra_articulos": ["art. 28", "R91"],
        "fundamento_destructivo": "El articulo 28 de la LFPDPPP establece los requisitos minimos de contenido de una solicitud ARCO. La ley no exige ni condiciona la validez de la solicitud al uso de un formato especifico del responsable. Ademas, el articulo 91 del Reglamento establece que cuando el responsable disponga de servicios de atencion al publico, podra atender las solicitudes ARCO a traves de dichos servicios, pudiendo acreditar la identidad del titular por los mismos medios usados para la prestacion de sus servicios. La presente solicitud cumple TODOS los requisitos del articulo 28. Cualquier pretension de invalidarla por no usar un formato corporativo carece de sustento legal y constituye una obstruccion al ejercicio de un derecho.",
    },
    {
        "id": "demand_more_docs",
        "tactica": "Solicitar documentacion adicional no prevista en la ley o encadenar requerimientos sucesivos de documentos",
        "contra_articulos": ["art. 28-II", "art. 32"],
        "fundamento_destructivo": "El articulo 28 fraccion II solo exige los documentos que acrediten la identidad del titular, los cuales ya se acompanan. El articulo 32 establece que el responsable puede requerir informacion adicional UNA SOLA VEZ dentro de los 5 dias siguientes a la recepcion, y el titular cuenta con 10 dias para atenderlo. No existe fundamento para encadenar requerimientos sucesivos ni para exigir documentos mas alla de la identificacion.",
    },
    {
        "id": "claim_ambiguous",
        "tactica": "Alegar que la solicitud es ambigua, oscura o imprecisa para no dar tramite",
        "contra_articulos": ["art. 28-IV", "art. 28-V", "art. 33"],
        "fundamento_destructivo": "La presente solicitud describe con claridad los datos personales involucrados y el derecho que se ejerce, cumpliendo los requisitos de las fracciones IV y V del articulo 28. Si el responsable considera que algun elemento es impreciso, debe prevenirlo dentro de los 5 dias conforme al articulo 32, no rechazar de plano. Toda negativa debe ser fundada y motivada conforme al articulo 33, identificando la causa especifica de improcedencia.",
    },
    {
        "id": "deny_jurisdiction",
        "tactica": "Negar la aplicabilidad de la LFPDPPP alegando que la empresa no esta sujeta a la ley, que tiene regimen especial o que los datos solicitados no estan protegidos",
        "contra_articulos": ["art. 1", "art. 5"],
        "fundamento_destructivo": "El articulo 1 de la LFPDPPP establece que la ley es de orden publico y de observancia general en toda la Republica, aplicable al tratamiento de datos personales por particulares. El articulo 5 define particulares como personas fisicas o morales de derecho privado. La empresa identificada en esta solicitud es un particular conforme a la ley y esta sujeta a todas sus disposiciones, sin excepcion.",
    },
    {
        "id": "claim_complied",
        "tactica": "Afirmar que ya se cumplio con la solicitud sin aportar evidencia verificable del cumplimiento efectivo",
        "contra_articulos": ["art. 22", "art. 23", "art. 24", "art. 25", "art. 26", "art. 31"],
        "fundamento_destructivo": "La simple afirmacion de cumplimiento no satisface la obligacion legal. El articulo 31 exige que la determinacion sea comunicada y, de ser procedente, se haga efectiva dentro de los 15 dias siguientes. Tratandose de acceso (art. 22), debe entregarse copia o puesta a disposicion de los datos. Tratandose de oposicion (art. 26), debe acreditarse el cese efectivo del tratamiento. Tratandose de cancelacion (art. 24), debe acreditarse el bloqueo y supresion. Cualquier respuesta que no contenga evidencia concreta y verificable del cumplimiento se tendra por no satisfactoria.",
    },
    {
        "id": "buck_pass_department",
        "tactica": "Deslindarse alegando que el area, sucursal o departamento receptor no es competente para atender solicitudes ARCO",
        "contra_articulos": ["art. 29", "art. 28"],
        "fundamento_destructivo": "El articulo 29 obliga al responsable a designar una persona o departamento de datos personales y a dar a conocer su identidad. Si el responsable no lo ha designado, la solicitud debe turnarse al area competente sin restringir su alcance. La presente solicitud se dirige al responsable legal, no a una sucursal, modulo o area operativa aislada. Si un area interna distinta conserva o trata los datos, la peticion debe canalizarse internamente al departamento competente. La falta de organizacion interna no es defensa frente al titular.",
    },
    {
        "id": "reject_id_format",
        "tactica": "Rechazar la identificacion presentada exigiendo un tipo especifico de documento no previsto en la ley",
        "contra_articulos": ["art. 28-II"],
        "fundamento_destructivo": "El articulo 28 fraccion II solo exige 'los documentos que acrediten la identidad del titular'. La identificacion oficial presentada (INE) es el documento oficial de identificacion por excelencia en Mexico segun la Ley General de Poblacion. Cualquier rechazo de este documento sin base en una disposicion legal especifica carece de sustento y constituye una denegacion infundada del derecho.",
    },
    {
        "id": "reject_notification_method",
        "tactica": "Desconocer el medio de notificacion senalado o exigir uno distinto como condicion para responder",
        "contra_articulos": ["art. 30", "art. 31"],
        "fundamento_destructivo": "El articulo 30 establece que las solicitudes pueden presentarse por medios electronicos o cualquier otro medio. La respuesta debe emitirse por el mismo medio, salvo que el titular senale otro. El medio senalado en esta solicitud es valido conforme a la ley. Exigir un medio distinto como condicion para responder constituye un obstaculo ilegitimo al ejercicio del derecho.",
    },
    {
        "id": "endless_delay",
        "tactica": "Dilatar la respuesta mas alla del plazo legal o aplicar ampliaciones sin justificacion o encadenadas",
        "contra_articulos": ["art. 31"],
        "fundamento_destructivo": "El articulo 31 establece un plazo maximo de 20 dias habiles para comunicar la determinacion. La ampliacion solo puede operar POR UNA UNICA VEZ, por un periodo igual, y DEBE NOTIFICARSE dentro del plazo original CON LA JUSTIFICACION correspondiente. Cualquier ampliacion que no cumpla estos requisitos es ilegal y la falta de respuesta dentro del plazo legal habilita la solicitud de proteccion de datos ante la Secretaria Anticorrupcion y Buen Gobierno conforme a los articulos 40 y 41.",
    },
    {
        "id": "former_relationship",
        "tactica": "Alegar que la persona ya no mantiene relacion con la empresa y por tanto no tiene derecho a ejercer ARCO",
        "contra_articulos": ["art. 1", "art. 21", "art. 25-III"],
        "fundamento_destructivo": "El articulo 1 establece que la ley aplica a TODO tratamiento de datos personales por particulares, sin condicionarlo a la vigencia de una relacion contractual. El articulo 21 reconoce el derecho ARCO a TODO titular, sin distinguir si la relacion esta vigente o concluida. De hecho, el articulo 25 fraccion III preve que los datos pueden conservarse exclusivamente para cumplir obligaciones legales; si la relacion concluyo, la conservacion debe estar plenamente justificada y, en caso contrario, procede la cancelacion.",
    },
    {
        "id": "affiliate_transfer_exception",
        "tactica": "Invoca la excepcion del articulo 36 fraccion III para transferir datos a afiliadas o subsidiarias sin consentimiento",
        "contra_articulos": ["art. 26-II", "art. 36-III", "art. 36 parrafo segundo", "R68", "R69", "R70"],
        "fundamento_destructivo": "El articulo 36 fraccion III preve una excepcion al consentimiento para transferencias entre sociedades controladoras, subsidiarias o afiliadas bajo control comun, pero esta excepcion NO es absoluta. La presente solicitud de oposicion, formulada expresamente conforme al articulo 26, fracciones I y II, deja sin efectos cualquier transferencia amparada en dicha excepcion cuando el titular manifiesta su voluntad contraria de manera expresa. El articulo 68 del Reglamento exige que TODA transferencia sea informada mediante el aviso de privacidad y se limite a la finalidad que la justifique. El articulo 69 del Reglamento establece que la carga de la prueba del cumplimiento recae en el responsable que transfiere y en el receptor. El articulo 70 del Reglamento exige que las transferencias intragrupo esten respaldadas por normas internas VINCULANTES que cumplan con la Ley; la mera pertenencia al mismo grupo corporativo no justifica la transferencia automatica.",
    },
    {
        "id": "legitimate_interest",
        "tactica": "Invoca un supuesto interes legitimo del responsable para justificar el tratamiento sin consentimiento o para negar la oposicion",
        "contra_articulos": ["art. 7", "art. 26-I", "R44"],
        "fundamento_destructivo": "La LFPDPPP mexicana no contempla el interes legitimo como base autonoma para el tratamiento, a diferencia del RGPD europeo. El articulo 7 exige consentimiento expreso y por escrito para datos patrimoniales, financieros y sensibles. El articulo 26 fraccion I permite la oposicion por causa legitima y situacion especifica del titular. Ademas, el articulo 44 del Reglamento prohibe expresamente utilizar medios enganosos o fraudulentos para tratar datos y establece que existe actuacion fraudulenta cuando: (I) hay dolo, mala fe o negligencia en la informacion al titular; (II) se vulnera la expectativa razonable de privacidad; o (III) las finalidades no son las informadas en el aviso. Si el responsable invoca un supuesto interes legitimo, debe identificar la base normativa CONCRETA en la legislacion mexicana que lo sustente; las referencias genericas a estandares extranjeros o conceptos no positivados en la LFPDPPP no constituyen fundamento valido.",
    },
    {
        "id": "necessary_purposes",
        "tactica": "Alegar que el tratamiento cuestionado es necesario para la relacion juridica y que sin el no puede prestarse el servicio",
        "contra_articulos": ["art. 11", "art. 15-IV", "art. 35", "art. 36", "R44", "R68"],
        "fundamento_destructivo": "El articulo 11 establece el principio de finalidad: los datos solo pueden tratarse para las finalidades informadas en el aviso de privacidad. El articulo 15 fraccion IV exige que el aviso distinga claramente entre finalidades necesarias y secundarias. La presente solicitud SOLO cuestiona finalidades secundarias o transferencias no indispensables. El articulo 44 del Reglamento prohibe las finalidades no informadas en el aviso y establece que constituye actuacion fraudulenta tratar datos para fines distintos a los informados. Si el responsable alega que el tratamiento objetado es necesario, debe identificar: (a) la obligacion legal concreta que lo exige; (b) su fuente normativa; (c) el dato especifico indispensable; y (d) por que es estrictamente necesario. Las afirmaciones genericas de necesidad no satisfacen esta carga argumentativa.",
    },
    {
        "id": "legal_retention_exception",
        "tactica": "Invoca las excepciones del articulo 25 para negar la cancelacion sin identificar la fraccion especifica ni justificar su aplicacion",
        "contra_articulos": ["art. 25", "art. 3"],
        "fundamento_destructivo": "El articulo 25 enumera las excepciones a la cancelacion de manera taxativa, no enunciativa. La negativa a cancelar debe identificar la fraccion concreta que se estima actualizada, el dato especifico afectado, la finalidad que justifica su conservacion y las pruebas pertinentes. El articulo 3 establece que los limites a los derechos ARCO deben interpretarse de manera restrictiva y no pueden vaciar el contenido esencial del derecho. Las invocaciones genericas al articulo 25 sin especificar fraccion, dato y finalidad constituyen una negativa infundada.",
    },
    {
        "id": "missing_privacy_notice",
        "tactica": "Ocultar o no tener disponible el aviso de privacidad, o tenerlo en un formato no accesible, como defensa para no responder",
        "contra_articulos": ["art. 15", "art. 16", "art. 17", "art. 18", "art. 19", "art. 20", "R44"],
        "fundamento_destructivo": "Los articulos 15 al 20 de la LFPDPPP regulan exhaustivamente el contenido, la forma y la puesta a disposicion del aviso de privacidad. La inexistencia, inaccesibilidad o incumplimiento del aviso no es una defensa frente al titular, sino una infraccion adicional del responsable. El articulo 44 del Reglamento es contundente: tratar datos para finalidades no informadas en el aviso constituye una actuacion fraudulenta. La falta de aviso de privacidad en los terminos de ley constituye una violacion a los principios de informacion y consentimiento (arts. 7, 12 y 15), sancionable conforme al articulo 58 de la Ley.",
    },
    {
        "id": "consentimiento_tacito",
        "tactica": "Alegar que el titular consintio tacitamente por no haberse opuesto al aviso de privacidad o por continuar usando el servicio",
        "contra_articulos": ["art. 7", "art. 8", "art. 9", "art. 10", "R44"],
        "fundamento_destructivo": "El articulo 8 establece que el consentimiento tacito solo es valido cuando el aviso de privacidad se pone a disposicion del titular y este no manifiesta su oposicion. Sin embargo, el articulo 7 exige consentimiento expreso y por escrito para datos patrimoniales, financieros y sensibles. El articulo 44 del Reglamento prohibe utilizar medios enganosos o fraudulentos, considerando como tal cuando exista dolo, mala fe o negligencia en la informacion proporcionada al titular. Ademas, el consentimiento tacito no puede interpretarse como una renuncia permanente e irrevocable a los derechos ARCO, que pueden ejercerse en cualquier momento. La continuacion en el uso del servicio no implica consentimiento para finalidades distintas de las estrictamente necesarias.",
    },
    {
        "id": "blocks_upload_corp_domain",
        "tactica": "Dificultar el ejercicio ARCO con barreras operativas: buzon unico, formularios web que exigen registro obligatorio, direcciones electronicas que rechazan archivos adjuntos mayores a 2 MB o que solo aceptan dominios corporativos",
        "contra_articulos": ["art. 29", "art. 30", "art. 34"],
        "fundamento_destructivo": "El articulo 30 de la Ley establece que las solicitudes pueden presentarse 'por medios electronicos o cualquier otro medio', sin que el responsable pueda imponer restricciones operativas que hagan nugatorio el ejercicio del derecho. El articulo 34 garantiza la gratuidad del procedimiento. Si el medio designado por el responsable rechaza, bloquea o no permite la recepcion efectiva de la solicitud, se entendera presentada por la via de hecho que resulte materialmente disponible, sin que el titular cargue con las consecuencias de la deficiencia operativa del responsable.",
    },
]


def counter_defenses(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Return tactical playbook to destroy specific corporate evasion strategies.

    Returns a structured map of evasion tactics found in the case context,
    each with its exact legal counter-article and destructive legal argument.
    The LLM uses this to craft specific, surgical counter-arguments in the draft.
    """
    case = _as_dict(case_data)
    responsible = _get(case, "responsable.nombre_legal", "el responsable")
    nat = _get(case, "responsable.naturaleza", "privado").strip().lower()
    rights = _right_names(case)

    has_oposicion = "oposicion" in rights
    has_cancelacion = "cancelacion" in rights
    has_acceso = "acceso" in rights
    has_limitacion = "limitacion_uso_divulgacion" in rights

    # Determine which tactics are relevant based on the rights being exercised
    relevant_ids: set[str] = set()

    # Universal tactics (always relevant)
    relevant_ids.update({"impose_format", "demand_more_docs", "claim_ambiguous", "deny_jurisdiction", "buck_pass_department", "reject_id_format", "reject_notification_method", "endless_delay", "former_relationship", "claim_complied", "blocks_upload_corp_domain"})

    if has_oposicion:
        relevant_ids.update({"affiliate_transfer_exception", "legitimate_interest", "necessary_purposes"})
    if has_cancelacion:
        relevant_ids.add("legal_retention_exception")
    if has_limitacion:
        relevant_ids.update({"necessary_purposes", "affiliate_transfer_exception"})

    relevant: list[dict[str, Any]] = []
    for t in CORPORATE_EVASION_TACTICS:
        if t["id"] in relevant_ids:
            entry = dict(t)
            # Inyectar texto completo de los articulos citados para que el LLM
            # no tenga que buscar nada mas — todo autónomo en una sola respuesta.
            article_texts: list[dict[str, str]] = []
            for art_ref in entry["contra_articulos"]:
                # Normalize: "art. 28-II" → "28", "art. 36 parrafo segundo" → "36", "R68" → "R68"
                normalized = art_ref.replace("art. ", "").split(" ")[0].split("-")[0].strip()
                # Resolver articulos LFPDPPP
                if normalized.isdigit() and normalized in ARTICLES:
                    article_texts.append({
                        "referencia": f"LFPDPPP art. {normalized}",
                        "titulo": ARTICLES[normalized]["title"],
                        "texto": ARTICLES[normalized]["use"],
                    })
                elif normalized.startswith("R") and normalized in REGULATION_ARTICLES:
                    article_texts.append({
                        "referencia": f"Reglamento LFPDPPP {normalized}",
                        "titulo": REGULATION_ARTICLES[normalized]["title"],
                        "texto": REGULATION_ARTICLES[normalized]["use"],
                    })
            entry["articulos_completos"] = article_texts
            relevant.append(entry)

    return {
        "ok": True,
        "total_defensas_identificadas": len(relevant),
        "defensas": relevant,
        "instrucciones_para_llm": (
            "CADA defensa incluye YA el texto completo de los articulos aplicables (campo 'articulos_completos'). "
            "NO necesitas consultar law_articles ni ningun otro recurso. "
            "TODO lo que necesitas para redactar la contra-defensa esta AQUI. "
            "Debes generar UN PARRAFO POR DEFENSA en la seccion 'DESESTIMACION DE DEFENSAS PREVISIBLES' del borrador. "
            "Cada parrafo debe: (1) nombrar la defensa, (2) citar el articulo con su texto, "
            "y (3) explicar por que es juridicamente improcedente. "
            "NO uses lenguaje generico ni inventes articulos. Usa EXACTAMENTE el texto proporcionado."
        ),
        "must_use_tools": ["audit_draft", "audit_argumentation", "assess_case"],
    }


def legal_graph(article_ids: list[str]) -> dict[str, Any]:
    """Query the legal relationship graph. Returns all semantic relationships
    for the given articles: what they require, limit, override, complement, etc.

    This eliminates hallucination risk by providing exact, pre-verified
    cross-references instead of letting the LLM infer relationships.
    """
    ids = [str(a) for a in article_ids]

    # Forward: relationships FROM these articles
    forward: dict[str, list[dict[str, str]]] = {}
    # Backward: relationships TO these articles (who references them)
    backward: dict[str, list[dict[str, str]]] = {}

    for aid in ids:
        if aid in LEGAL_GRAPH:
            forward[aid] = LEGAL_GRAPH[aid]

    for src, rels in LEGAL_GRAPH.items():
        for rel in rels:
            if rel["target"] in ids or rel["target"] == ids[0] if ids else False:
                backward.setdefault(rel["target"], []).append({
                    "source": src,
                    "type": rel["type"],
                    "reason": rel["reason"],
                })

    # Collect all referenced article IDs (forward + backward) for the LLM
    # to look up via law_articles if it needs full text.
    # We DON'T inject text here — the graph is an index, not a content store.
    all_refs: set[str] = set()
    for rels in forward.values():
        for r in rels:
            all_refs.add(r["target"])
    for rels in backward.values():
        for r in rels:
            all_refs.add(r["source"])

    return {
        "ok": True,
        "articles_consulted": ids,
        "relationships_forward": forward,
        "relationships_backward": backward,
        "articles_to_lookup": sorted(all_refs),
        "instrucciones": (
            "Las relaciones arriba describen EXACTAMENTE como interactuan los articulos. "
            "'requires' — A no puede aplicarse sin B (fundamento). "
            "'limits' — A restringe el alcance de B. "
            "'overrides' — A prevalece sobre B en conflicto. "
            "'complements' — A detalla/expande B. "
            "'procedural' — A es el paso siguiente a B. "
            "'defines' — A define terminos usados en B. "
            "'excepts' — A lista excepciones a B. "
            "SI necesitas el texto completo de algun articulo listado en 'articles_to_lookup', "
            "llama a law_articles(['X', 'Y', ...]) para obtenerlo. "
            "NO inyectes texto de articulos en el grafo — el grafo es SOLO navegacion."
        ),
        "must_use_tools": ["law_articles", "audit_draft", "audit_argumentation"],
    }


# ═══════════════════════════════════════════════════════════════════════
# GRAPH RAG — semantic communities, summaries, global/local search
# ═══════════════════════════════════════════════════════════════════════

# Community detection: nodes grouped by legal domain + graph structure
# Cross-community edges are counted to determine inter-community relevance.
_COMMUNITIES: dict[str, dict[str, Any]] = {
    "c_general": {
        "id": "c_general",
        "title": "Disposiciones Generales y Principios",
        "description": "Objeto de la ley, definiciones, limites generales, ambito de aplicacion. Fundamento constitucional de proteccion de datos.",
        "nodes": ["1", "2", "3", "4", "5", "CPEUM-1", "CPEUM-16", "CPEUM-103"],
        "instrumentos": ["LFPDPPP 2025", "CPEUM"],
    },
    "c_consent": {
        "id": "c_consent",
        "title": "Consentimiento, Licitud y Datos Sensibles",
        "description": "Principios de licitud, consentimiento expreso y tacito, excepciones, datos sensibles, calidad, responsabilidad, deber de informacion y aviso de privacidad.",
        "nodes": ["6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "R44"],
        "instrumentos": ["LFPDPPP 2025", "Reglamento LFPDPPP 2011"],
    },
    "c_arco_rights": {
        "id": "c_arco_rights",
        "title": "Derechos ARCO",
        "description": "Habilitacion de derechos de Acceso, Rectificacion, Cancelacion y Oposicion. Limites, excepciones y alcance de cada derecho. Relacion con representante legal.",
        "nodes": ["21", "22", "23", "24", "25", "26", "27"],
        "instrumentos": ["LFPDPPP 2025"],
    },
    "c_arco_procedure": {
        "id": "c_arco_procedure",
        "title": "Procedimiento ARCO ante el Responsable",
        "description": "Requisitos de la solicitud, persona o departamento designado, medios de presentacion, plazos de respuesta, prevencion, improcedencia, gratuidad. Incluye articulos del Reglamento sobre canales validos de recepcion.",
        "nodes": ["28", "29", "30", "31", "32", "33", "34", "R91"],
        "instrumentos": ["LFPDPPP 2025", "Reglamento LFPDPPP 2011"],
    },
    "c_transfers": {
        "id": "c_transfers",
        "title": "Transferencias de Datos Personales",
        "description": "Regimen de transferencias nacionales e internacionales, consentimiento requerido, excepciones, carga de la prueba, normas internas vinculantes para transferencias intragrupo.",
        "nodes": ["35", "36", "R68", "R69", "R70", "R74"],
        "instrumentos": ["LFPDPPP 2025", "Reglamento LFPDPPP 2011"],
    },
    "c_selfreg": {
        "id": "c_selfreg",
        "title": "Autorregulacion Vinculante",
        "description": "Esquemas voluntarios de autorregulacion, registro obligatorio ante la autoridad, codigos deontologicos, sellos de confianza. No sustituyen ni limitan la Ley.",
        "nodes": ["37", "R86"],
        "instrumentos": ["LFPDPPP 2025", "Reglamento LFPDPPP 2011"],
    },
    "c_secretaria": {
        "id": "c_secretaria",
        "title": "Secretaria Anticorrupcion y Procedimientos de Proteccion",
        "description": "Funciones de la Secretaria, solicitud de proteccion de datos, improcedencia, sobreseimiento, conciliacion, resoluciones, publicidad de resoluciones, verificacion, acceso a informacion en verificacion.",
        "nodes": ["38", "40", "41", "47", "48", "49", "50", "52", "53", "54", "55"],
        "instrumentos": ["LFPDPPP 2025"],
    },
    "c_sanctions": {
        "id": "c_sanctions",
        "title": "Infracciones, Sanciones y Delitos",
        "description": "Procedimiento sancionador, catalogo de infracciones, multas, graduacion de sanciones, agravantes por datos sensibles, delitos penales por tratamiento indebido.",
        "nodes": ["56", "58", "59", "60"],
        "instrumentos": ["LFPDPPP 2025"],
    },
    "c_lfpa": {
        "id": "c_lfpa",
        "title": "Procedimiento Administrativo (LFPA)",
        "description": "Supletoriedad de la LFPA en procedimientos ante la Secretaria, elementos del acto administrativo, notificaciones, recurso de revision como paso previo opcional al amparo.",
        "nodes": ["LFPA-1", "LFPA-3", "LFPA-35", "LFPA-38", "LFPA-39"],
        "instrumentos": ["LFPA"],
    },
    "c_amparo": {
        "id": "c_amparo",
        "title": "Juicio de Amparo",
        "description": "Procedencia del amparo indirecto ante Juzgado de Distrito contra resoluciones de la Secretaria. Plazos en dias habiles, suspension del acto reclamado, definitividad, improcedencia.",
        "nodes": ["51", "LA-17", "LA-19", "LA-61", "LA-107", "LA-125", "LA-128"],
        "instrumentos": ["LFPDPPP 2025", "Ley de Amparo"],
    },
    "c_security": {
        "id": "c_security",
        "title": "Seguridad y Confidencialidad",
        "description": "Medidas de seguridad administrativas, tecnicas y fisicas. Vulneraciones de seguridad, deber de confidencialidad. Indemnizacion por danos.",
        "nodes": ["18", "19", "20"],
        "instrumentos": ["LFPDPPP 2025"],
    },
}

# Compute cross-community edges for relevance scoring
def _build_community_graph() -> dict[str, dict[str, int]]:
    """Count cross-community edges for inter-community relevance."""
    node_to_community: dict[str, str] = {}
    for cid, cdata in _COMMUNITIES.items():
        for node in cdata["nodes"]:
            node_to_community[node] = cid

    cross: dict[str, dict[str, int]] = {cid: {} for cid in _COMMUNITIES}
    for src_cid in _COMMUNITIES:
        for src_node in _COMMUNITIES[src_cid]["nodes"]:
            if src_node not in LEGAL_GRAPH:
                continue
            for rel in LEGAL_GRAPH[src_node]:
                tgt_node = rel["target"]
                tgt_cid = node_to_community.get(tgt_node)
                if tgt_cid and tgt_cid != src_cid:
                    cross[src_cid][tgt_cid] = cross[src_cid].get(tgt_cid, 0) + 1

    return cross

_COMMUNITY_CROSS = _build_community_graph()


def _community_summary(cid: str) -> str:
    """Generate natural language summary of a community and its connections."""
    cdata = _COMMUNITIES[cid]
    node_count = len(cdata["nodes"])
    instruments = ", ".join(cdata["instrumentos"])

    # Count internal relationships
    internal = 0
    external: dict[str, int] = {}
    for node in cdata["nodes"]:
        if node not in LEGAL_GRAPH:
            continue
        for rel in LEGAL_GRAPH[node]:
            target = rel["target"]
            target_cid = None
            for tc, td in _COMMUNITIES.items():
                if target in td["nodes"]:
                    target_cid = tc
                    break
            if target_cid == cid:
                internal += 1
            elif target_cid:
                ext_name = _COMMUNITIES[target_cid]["title"].split(" ")[:3]
                key = " ".join(ext_name)
                external[key] = external.get(key, 0) + 1

    # Get article titles
    titles: list[str] = []
    for node in cdata["nodes"]:
        if node in ARTICLES:
            titles.append(f"art. {node} ({ARTICLES[node]['title']})")
        elif node in REGULATION_ARTICLES:
            titles.append(f"{node} ({REGULATION_ARTICLES[node]['title']})")

    summary = (
        f"COMUNIDAD: {cdata['title']}\n"
        f"Instrumentos: {instruments}\n"
        f"Nodos: {node_count} articulos\n"
        f"Relaciones internas: {internal}\n"
    )
    if external:
        summary += "Conexiones externas:\n"
        for ext_name, count in sorted(external.items(), key=lambda x: -x[1]):
            summary += f"  → {ext_name}... ({count} vinculos)\n"

    summary += "\nArticulos contenidos:\n"
    for t in titles:
        summary += f"  • {t}\n"

    summary += f"\nDESCRIPCION: {cdata['description']}"
    return summary


def semantic_search(query: str) -> dict[str, Any]:
    """Global semantic search across the legal graph communities.

    Given a natural language query, returns the most relevant communities,
    their summaries, and the specific articles most likely to apply.

    Uses keyword matching against community descriptions, article titles,
    and relationship reasons to rank communities by relevance.
    """
    q = query.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    tokens = set(q.split())

    # Query expansion: normalize common legal verbs/nouns to their canonical form
    _EXPANSIONS: dict[str, list[str]] = {
        "oposicion": ["oponerme", "oponerse", "opongo", "opone", "oponen", "oposicion", "opongo"],
        "transferencia": ["transferir", "transfieran", "transferencia", "transferencias", "transferido", "transfiere"],
        "cancelacion": ["cancelar", "cancelacion", "cancele", "cancelo", "cancelado"],
        "rectificacion": ["rectificar", "rectificacion", "rectifique", "rectifico"],
        "acceso": ["acceder", "acceso", "acceda", "accedo", "accediendo"],
        "datos_personales": ["datos", "dato", "personales", "personal", "informacion", "privacidad"],
        "sancion": ["sancion", "sanciones", "multa", "multas", "sancionar", "infraccion", "infracciones"],
        "amparo": ["amparo", "ampararme", "ampararse", "juicio", "demanda", "demandar", "juzgado", "tribunal"],
        "consentimiento": ["consentimiento", "consentir", "consiento", "autorizar", "autorizacion", "permiso", "permitir"],
        "aviso_privacidad": ["aviso", "privacidad", "notice", "politica"],
        "secretaria": ["secretaria", "anticorrupcion", "autoridad", "gobierno", "proteccion", "denuncia", "denunciar", "queja"],
        "afiliadas": ["afiliada", "afiliadas", "subsidiaria", "subsidiarias", "filial", "grupo", "controladora", "matriz"],
        "finalidades": ["finalidad", "finalidades", "proposito", "propositos", "uso", "usos", "fines"],
    }
    expanded_tokens: set[str] = set(tokens)
    for token in list(tokens):
        for canonical, variants in _EXPANSIONS.items():
            if token in variants:
                expanded_tokens.add(canonical)
                for v in variants:
                    expanded_tokens.add(v)

    tokens = expanded_tokens

    # IDF-like normalization: common tokens (like "datos") appear everywhere
    # and should not dominate. Rare tokens (like "transferencia", "afiliadas") are
    # more discriminative and should have higher weight.
    _strip = lambda s: s.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    _token_freq: dict[str, int] = {}
    for cdata in _COMMUNITIES.values():
        desc = _strip(cdata["description"]) + " " + _strip(cdata["title"])
        for token in tokens:
            if token in desc:
                _token_freq[token] = _token_freq.get(token, 0) + 1
    # Max token weight = 5.0, min = 0.5. Rare tokens get higher weight.
    _token_weights = {
        t: max(0.5, 5.0 / max(1, _token_freq.get(t, 1)))
        for t in tokens
    }

    # Score each community
    scores: list[tuple[str, float]] = []
    for cid, cdata in _COMMUNITIES.items():
        score = 0.0
        desc_lower = _strip(cdata["description"])
        title_lower = _strip(cdata["title"])

        # Direct keyword match in title/description
        for token in tokens:
            weight = _token_weights.get(token, 1.0)
            if token in title_lower:
                score += 3.0 * weight
            if token in desc_lower:
                score += 1.0 * weight

        # Match against article titles and texts in this community
        article_matches: list[str] = []
        for node in cdata["nodes"]:
            if node in ARTICLES:
                art_text = _strip(ARTICLES[node]["title"] + " " + ARTICLES[node]["use"])
                node_weight = 0.0
                for token in tokens:
                    if token in art_text:
                        node_weight += 2.0 * _token_weights.get(token, 1.0)
                if node_weight > 0:
                    article_matches.append(node)
                    score += node_weight
            elif node in REGULATION_ARTICLES:
                reg_text = _strip(REGULATION_ARTICLES[node]["title"] + " " + REGULATION_ARTICLES[node]["use"])
                node_weight = 0.0
                for token in tokens:
                    if token in reg_text:
                        node_weight += 2.0 * _token_weights.get(token, 1.0)
                if node_weight > 0:
                    article_matches.append(node)
                    score += node_weight

        # Match against relationship reasons (cross-community context)
        for node in cdata["nodes"]:
            if node not in LEGAL_GRAPH:
                continue
            for rel in LEGAL_GRAPH[node]:
                reason = rel["reason"].lower()
                for token in tokens:
                    if token in reason:
                        score += 0.5

        if score > 0:
            scores.append((cid, score))

    scores.sort(key=lambda x: -x[1])

    results: list[dict[str, Any]] = []
    for cid, score in scores:
        cdata = _COMMUNITIES[cid]
        # Find best matching articles in this community
        best_articles: list[str] = []
        for node in cdata["nodes"]:
            match_score = 0.0
            if node in ARTICLES:
                art_text = _strip(ARTICLES[node]["title"] + " " + ARTICLES[node]["use"])
                for token in tokens:
                    if token in art_text:
                        match_score += 1.0
            elif node in REGULATION_ARTICLES:
                reg_text = _strip(REGULATION_ARTICLES[node]["title"] + " " + REGULATION_ARTICLES[node]["use"])
                for token in tokens:
                    if token in reg_text:
                        match_score += 1.0
            if match_score > 0:
                best_articles.append(node)

        results.append({
            "community_id": cid,
            "community_title": cdata["title"],
            "relevance": round(score, 2),
            "instrumentos": cdata["instrumentos"],
            "description": cdata["description"],
            "matching_articles": best_articles[:5],
            "all_nodes": cdata["nodes"],
        })

    top_ids = [r["community_id"] for r in results[:3]]

    return {
        "ok": True,
        "query": query,
        "communities_found": len(results),
        "top_communities": results[:3],
        "instrucciones": (
            "Las comunidades arriba son las mas relevantes para tu consulta. "
            "Para cada comunidad relevante, llama a community_detail(community_id) "
            "para obtener el resumen completo, todos los articulos y sus relaciones. "
            "Luego usa law_articles para obtener el texto completo de los articulos que necesites. "
            "Flujo: semantic_search → community_detail → law_articles → construye argumento."
        ),
        "must_use_tools": ["community_detail", "law_articles"],
        "suggested_next_communities": top_ids if top_ids else ["c_general"],
    }


def community_detail(community_id: str) -> dict[str, Any]:
    """Returns the full detail of a community: summary, all articles with text,
    internal relationships, and cross-community connections.
    """
    if community_id not in _COMMUNITIES:
        return {
            "ok": False,
            "error": f"Comunidad '{community_id}' no encontrada. Comunidades validas: {list(_COMMUNITIES.keys())}",
        }

    cdata = _COMMUNITIES[community_id]
    nodes = cdata["nodes"]

    # Collect all relationships within and from this community
    internal_rels: list[dict[str, str]] = []
    external_rels: dict[str, list[dict[str, str]]] = {}
    all_targets: set[str] = set()

    for node in nodes:
        if node not in LEGAL_GRAPH:
            continue
        for rel in LEGAL_GRAPH[node]:
            target = rel["target"]
            all_targets.add(target)
            # Determine if target is in the same community
            target_cid = None
            for tc, td in _COMMUNITIES.items():
                if target in td["nodes"]:
                    target_cid = tc
                    break
            entry = {"source": node, "type": rel["type"], "target": target, "reason": rel["reason"]}
            if target_cid == community_id:
                internal_rels.append(entry)
            else:
                ext_label = target_cid or "externo"
                external_rels.setdefault(ext_label, []).append(entry)

    # Get article texts for all nodes
    bundle = article_bundle(nodes)

    # Generate summary
    summary = _community_summary(community_id)

    # Cross-community stats
    cross_stats = _COMMUNITY_CROSS.get(community_id, {})

    return {
        "ok": True,
        "community_id": community_id,
        "title": cdata["title"],
        "summary": summary,
        "node_count": len(nodes),
        "articles": bundle["articles"],
        "internal_relationships": internal_rels,
        "external_connections": {
            ext_label: {"count": len(rels), "sample_relationships": rels[:3]}
            for ext_label, rels in external_rels.items()
        },
        "cross_community_stats": cross_stats,
        "instrumentos": cdata["instrumentos"],
        "instrucciones": (
            f"Esta comunidad cubre {len(nodes)} articulos sobre {cdata['title']}. "
            "Los articulos completos estan en el campo 'articles'. "
            "Las relaciones internas muestran como interactuan los articulos DENTRO de esta comunidad. "
            "Las conexiones externas muestran vinculos con OTRAS comunidades. "
            "Usa law_articles para obtener texto completo de articulos en otras comunidades si los necesitas."
        ),
        "must_use_tools": ["law_articles", "legal_graph"],
    }

