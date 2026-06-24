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
    PENAL_ARTICLES,
    RIGHTS,
    SANCTION_ARTICLES,
    SECRETARIA_ARTICLES,
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


def _right_names(case: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in _rights(case):
        if isinstance(item, dict) and isinstance(item.get("tipo"), str):
            names.append(item["tipo"].strip().lower())
        elif isinstance(item, str):
            names.append(item.strip().lower())
    return names


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
    """Return controlled article summaries."""
    ids = article_ids or sorted(ARTICLES, key=lambda x: int(x))
    selected = {str(i): ARTICLES[str(i)] for i in ids if str(i) in ARTICLES}
    return {
        "source": DECREE_SOURCE,
        "authority_for_particulares": AUTHORITY,
        "articles": selected,
    }


def select_legal_basis(case_data: dict[str, Any] | str) -> dict[str, Any]:
    """Select articles that are in scope for the requested rights and facts."""
    case = _as_dict(case_data)
    selected = list(GENERAL_LIMIT_ARTICLES + BASE_ARTICLES)
    unknown_rights: list[str] = []
    non_arco_complements: list[str] = []

    for name in _right_names(case):
        if name not in VALID_RIGHTS:
            unknown_rights.append(name)
            continue
        selected.extend(RIGHTS[name]["articles"])
        if RIGHTS[name].get("not_arco"):
            non_arco_complements.append(name)

    data_items = case.get("datos_personales", [])
    has_sensitive = any(
        isinstance(item, dict) and item.get("sensible") is True
        for item in (data_items if isinstance(data_items, list) else [])
    )
    has_transfer = any(
        name in {"limitacion_uso_divulgacion", "revocacion_consentimiento"}
        for name in _right_names(case)
    ) or _present(case.get("transferencias"))
    facts_text = json.dumps(case, ensure_ascii=False).lower()
    has_penal_trigger = any(
        token in facts_text
        for token in ("vulneracion de seguridad", "filtracion", "fuga de datos", "lucro", "engaño", "engano")
    )

    if has_sensitive:
        selected.extend(SENSITIVE_ARTICLES)
    if has_transfer:
        selected.extend(TRANSFER_ARTICLES)

    selected.extend(SECRETARIA_ARTICLES)
    selected.extend(SANCTION_ARTICLES)
    if has_penal_trigger:
        selected.extend(PENAL_ARTICLES)
    selected = _dedupe(selected)

    return {
        "ok": True,
        "source": DECREE_SOURCE,
        "authority": AUTHORITY,
        "selected_articles": selected,
        "article_summaries": {i: ARTICLES[i] for i in selected if i in ARTICLES},
        "unknown_rights": unknown_rights,
        "non_arco_complements": non_arco_complements,
        "notes": [
            "Limitacion de uso/divulgacion y revocacion de consentimiento no son derechos ARCO autonomos.",
            "Las sanciones no son automaticas: dependen de infraccion concreta y procedimiento.",
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
        blockers.append({
            "code": "wrong_legal_regime",
            "message": "La LFPDPPP aplica a sujetos regulados privados. Si el responsable no es privado, debe usarse el regimen juridico correspondiente antes de redactar.",
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
    return ", ".join(f"articulo {i}" for i in sorted(ids, key=int))


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
        if name == "oposicion":
            if right.get("supuesto_oposicion") == "tratamiento_automatizado":
                right_sections.append(
                    "### Oposicion por tratamiento automatizado\n\n"
                    f"Solicito el cese u oposicion respecto de {petition}. "
                    f"El tratamiento automatizado identificado consiste en: {right.get('descripcion_tratamiento_automatizado', '[tratamiento automatizado]')}. "
                    f"El efecto juridico no deseado o afectacion significativa es: {right.get('efecto_juridico_o_afectacion_significativa', '[efecto o afectacion]')}. "
                    f"Los aspectos personales evaluados o inferidos son: {right.get('aspectos_personales_evaluados', '[aspectos evaluados]')}. "
                    "Solicito que se indique si existe intervencion humana significativa, la logica general aplicada y la base juridica concreta del tratamiento."
                )
            else:
                right_sections.append(
                    "### Oposicion\n\n"
                    f"Solicito el cese del tratamiento consistente en {petition}. "
                    f"La causa legitima es: {right.get('causa_legitima_oposicion', '[causa legitima]')}. "
                    f"Mi situacion especifica es: {right.get('situacion_especifica_oposicion', '[situacion especifica]')}. "
                    f"La persistencia del tratamiento puede causarme: {right.get('dano_o_perjuicio_oposicion', '[dano o perjuicio]')}. "
                    "Si consideran que el tratamiento es necesario para cumplir una obligacion legal, solicito identificar la obligacion concreta, su fuente normativa, el dato indispensable y la finalidad estrictamente necesaria."
                )
        elif name == "cancelacion":
            right_sections.append(
                "### Cancelacion\n\n"
                f"Solicito la cancelacion de {petition}, con el bloqueo previo que legalmente corresponda y la supresion posterior al concluir el plazo aplicable. "
                "Si estiman actualizada alguna excepcion del articulo 25, solicito identificar la fraccion aplicable, el dato afectado, la finalidad que justifica su conservacion y las pruebas pertinentes."
            )
        elif name == "rectificacion":
            right_sections.append(
                "### Rectificacion\n\n"
                f"Solicito rectificar {right.get('dato_actual_rectificacion', '[dato actual]')} para que conste como {right.get('dato_correcto_rectificacion', '[dato correcto]')}. "
                f"Anexo como soporte: {right.get('documento_soporte_rectificacion', '[documento soporte]')}."
            )
        elif name == "acceso":
            right_sections.append(
                "### Acceso\n\n"
                f"Solicito {petition}. Esto incluye confirmacion de tratamiento, copia o puesta a disposicion de mis datos personales, finalidades, categorias de datos, origen cuando no provengan directamente de mi, transferencias ya realizadas o previstas, terceros receptores o categorias de receptores y plazo o criterio de conservacion."
            )
        elif name == "limitacion_uso_divulgacion":
            right_sections.append(
                "### Limitacion de uso y divulgacion\n\n"
                f"De forma complementaria, solicito limitar el uso y divulgacion de mis datos para {petition}. "
                "Esta peticion se formula respecto de finalidades secundarias, mercadotecnia, publicidad, prospeccion comercial, perfilamiento no necesario y transferencias futuras o no indispensables."
            )
        elif name == "revocacion_consentimiento":
            right_sections.append(
                "### Revocacion de consentimiento\n\n"
                f"Solicito revocar mi consentimiento respecto de {petition}, sin efectos retroactivos y sin afectar tratamientos estrictamente necesarios por ley o por la relacion juridica aplicable."
            )

    folio_text = f" Referencia de localizacion: {folio}." if folio else ""
    draft = f"""{ciudad}, {fecha}

{responsable}
Area o departamento de datos personales
{canal}
Presente.

## Asunto

Solicitud de ejercicio de derechos ARCO y peticiones complementarias en materia de proteccion de datos personales.

## Titular y medio de notificacion

Yo, {titular}, por mi propio derecho, senalo como medio para recibir notificaciones {medio}. Acredito mi identidad con copia de {id_tipo}, que se acompana como anexo, conforme al articulo 28, fraccion II, de la Ley.

## Relacion juridica y localizacion de datos

Mantengo o mantuve relacion con {responsable} consistente en: {relacion}.{folio_text}

La solicitud se dirige al responsable legal identificado en su aviso de privacidad vigente, no a una sucursal, modulo, punto de venta o area operativa aislada. En caso de que un area interna distinta conserve o trate los datos, solicito que esta peticion sea canalizada internamente al departamento competente sin restringir indebidamente el alcance de la solicitud.

Para evitar cualquier ambiguedad sobre la persona responsable, hago constar que la identidad, domicilio y canal de atencion se tomaron del aviso de privacidad consultado en {aviso_ref} el {aviso_fecha}.

Si el responsable no ha designado persona o departamento de datos personales, solicito que esta comunicacion sea turnada al area competente y que se me informe el dato de contacto designado para el tramite, conforme al articulo 29 de la Ley.

## Datos personales involucrados

{_data_list(case)}

## Fundamento

La presente solicitud se formula con fundamento en la Ley Federal de Proteccion de Datos Personales en Posesion de los Particulares (en lo sucesivo, la Ley), particularmente en {_format_articles(basis_ids)}. Para efectos de la Ley, la autoridad competente referida como Secretaria es la {AUTHORITY}. Reconozco que el ejercicio de estos derechos se encuentra sujeto a los limites del articulo 3 de la Ley; si el responsable invoca alguno, solicito identificar el limite concreto, su base normativa, la necesidad de aplicarlo y los datos afectados.

## Derechos y peticiones

{chr(10).join(right_sections)}

## Acuse y gratuidad

Solicito que se acuse recibo de esta solicitud por el mismo medio de envio o por el medio senalado para notificaciones, indicando fecha de recepcion, hora, folio si existe y area o persona que la recibe. Hago valer que el ejercicio de los derechos ARCO es gratuito conforme al articulo 34 de la Ley, sin perjuicio de costos estrictamente limitados a reproduccion, copias o envio cuando legalmente procedan y se justifiquen.

## Negativa total o parcial

Toda negativa total o parcial debera comunicarse dentro del plazo legal, por el mismo medio senalado para notificaciones, expresando de forma fundada y motivada la causa especifica de improcedencia prevista en el articulo 33 de la Ley y acompanando, en su caso, las pruebas pertinentes que sustenten dicha determinacion.

## Plazos

Solicito que la determinacion correspondiente sea comunicada dentro del plazo maximo de veinte dias habiles contado desde la recepcion de esta solicitud y que, de resultar procedente, se haga efectiva dentro de los quince dias habiles siguientes a la comunicacion de la respuesta, conforme al articulo 31 de la Ley. Cualquier ampliacion debera notificarse dentro del plazo aplicable, justificarse por las circunstancias del caso y solo podra operar por una vez y por un periodo igual.

## Reserva de derechos

En caso de falta de respuesta, respuesta incompleta, negativa injustificada, entrega en formato incomprensible o cumplimiento defectuoso, me reservo el derecho de presentar solicitud de proteccion de datos ante la {AUTHORITY}, en terminos de los articulos 40 y 41 de la Ley, dentro del plazo aplicable y acompanando la constancia de presentacion o recepcion de esta solicitud. Tambien me reservo el derecho de solicitar la verificacion que corresponda conforme al articulo 54 y de acudir al juicio de amparo contra resoluciones de la Secretaria en terminos del articulo 51, sin perjuicio de los derechos indemnizatorios previstos en el articulo 53 cuando procedan.

Se hace constar que las conductas de incumplimiento, negligencia, dolo, tratamiento contrario a los principios de la Ley, transferencia indebida, uso ilegitimo, obstruccion de verificacion o afectacion al ejercicio de derechos ARCO pueden actualizar infracciones previstas en el articulo 58, sancionables conforme al articulo 59, segun la conducta especifica que en su caso se acredite mediante el procedimiento correspondiente.

## Anexos

{_format_anexos(case)}

Atentamente,

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
            "Caso listo: revisa el borrador y usa audit_draft para verificarlo."
            if validation["ready_to_draft"]
            else "Caso no listo. Se genero un draft_preview con marcadores [FALTA: campo]. Completa los campos faltantes y revalida."
        ),
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
    if fatal_blockers:
        nivel = "insostenible"
        descripcion_nivel = (
            "El caso tiene vicios fatales que impiden su tramite. "
            "Si se presenta asi, el responsable puede rechazarlo de plano "
            "por no identificar correctamente al sujeto regulado, "
            "por carecer de fuente de aviso de privacidad verificable "
            "o por no dirigirse al canal ARCO oficial."
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
    }
