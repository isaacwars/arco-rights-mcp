# ARCO MCP — Ejerce tus derechos ARCO sin abogado

Servidor MCP anti-alucinación para redactar, validar y auditar solicitudes de derechos ARCO (Acceso, Rectificación, Cancelación, Oposición) contra cualquier empresa privada en México. Basado en la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP) del decreto del 20 de marzo de 2025.

---

## ⚠️ Aviso importante

ARCO MCP es una herramienta de asistencia técnica. **No sustituye el consejo de un abogado.** El autor no es abogado ni despacho jurídico. Este software aplica la LFPDPPP de forma automatizada, pero:

- No garantiza resultados legales
- No asume responsabilidad por el uso que se le dé
- No constituye asesoría jurídica

**Siempre verifica el borrador final con un profesional del derecho antes de presentarlo.** La ley puede tener interpretaciones que una herramienta automatizada no puede anticipar. Este proyecto es altruista: su único fin es facilitar el acceso a los derechos ARCO para cualquier persona en México.

---

## ⚖️ ¿Qué necesitas para que tu solicitud ARCO sea válida?

La LFPDPPP exige **7 requisitos** (arts. 15, 28). Si falta uno, la empresa puede rechazar tu solicitud:

| # | Requisito | Fundamento |
|---|-----------|------------|
| 1 | **Acreditar tu identidad** con copia de identificación oficial vigente | Art. 28, frac. II |
| 2 | **Señalar un medio para recibir notificaciones** (correo electrónico o domicilio) | Art. 28, frac. I |
| 3 | **Describir claramente los datos personales** involucrados (salvo si solo pides acceso) | Art. 28, frac. III |
| 4 | **Especificar el derecho que ejerces** (acceso, rectificación, cancelación u oposición) | Art. 28, frac. IV |
| 5 | **Identificar al responsable legal** con el nombre exacto que aparece en su aviso de privacidad (NO el nombre comercial) | Art. 15 |
| 6 | **Usar el canal ARCO oficial** que el responsable publica en su aviso de privacidad | Art. 15 |
| 7 | **La autoridad es la Secretaría Anticorrupción y Buen Gobierno** (NO el INAI — la ley cambió en 2025) | Art. 38 |

Si tu solicitud cumple estos 7 requisitos, el responsable tiene **20 días hábiles** para responder (art. 31). Si no responde o responde mal, puedes acudir a la Secretaría (art. 40) y, en última instancia, al amparo (art. 51).

---

## 🛡️ ¿Qué hace este MCP?

ARCO MCP **no inventa** — consulta matrices legales controladas extraídas directamente del decreto. El LLM que lo use no puede alucinar artículos, autoridades ni plazos.

| Herramienta | Función |
|------------|---------|
| `process_case` | Pipeline completo: validar → fundamentar → argumentar → redactar en una sola llamada |
| `audit_draft` | Auditar un borrador: detecta 24 patrones de errores jurídicos (INAI, multas automáticas, plazos incorrectos, fracciones equivocadas) |
| `audit_argumentation` | Auditar vicios lógicos: detecta 14 falacias y errores argumentativos documentados por la UNAM |
| `assess_case` | Valorar solidez jurídica: nivel (irrefutable/sólido/débil/insostenible) + implicaciones legales + pronóstico |
| `validate_case` | Validar datos del caso: campos faltantes, placeholders, datos sensibles no marcados |
| `deadline_timeline` | Calcular plazos en días hábiles desde la solicitud hasta el amparo |
| `escalation_basis` | Fundamento legal para escalar ante la Secretaría o vía amparo (LFPDPPP + LFPA + Ley de Amparo + Constitución) |

Si el LLM pasa texto de borrador a una herramienta que espera JSON, el MCP lo **rechaza automáticamente** y le indica qué herramienta usar.

---

## 📦 Instalación

```bash
pipx install arco-rights-mcp
```

### Configuración en tu cliente MCP

**OpenCode:**
```json
{
  "mcpServers": {
    "arco-rights": {
      "command": "arco-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

**Claude Desktop / Gemini CLI:**
```json
{
  "mcpServers": {
    "arco-rights": {
      "command": "arco-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

---

## 🎯 Flujo recomendado

1. **Obtén el aviso de privacidad vigente** del responsable (su sitio oficial)
2. **Carga `arco://law/overview`** para entender las 4 leyes que aplican
3. **Usa `process_case`** con tu caso en JSON para validar y generar borrador
4. **Pasa el borrador por `audit_draft`** para detectar errores jurídicos
5. **Pasa el borrador por `audit_argumentation`** para detectar vicios lógicos
6. **Refina el estilo** con `arco://writing/style` (método CRAC + 5 reglas de oro)
7. **Envía por el canal ARCO oficial** y conserva el acuse de recibo

---

## 📚 Fuentes académicas

- Fernández Ruiz, G. *Argumentación y lenguaje jurídico. Aplicación al análisis de una sentencia de la SCJN.* 2ª ed. UNAM-IIJ, 2017.
- Malem Seña, J.F. "El lenguaje de las sentencias". *Reforma Judicial. Revista Mexicana de Justicia*, IIJ-UNAM, núm. 7, 2006.
- LFPDPPP: Decreto del 20 de marzo de 2025 (DOF).

---

## 🔒 Licencia

ARCO MCP se distribuye bajo **AGPLv3**. Esto significa:

- ✅ Puedes usarlo gratis para fines personales, académicos y altruistas
- ✅ Puedes modificarlo y compartirlo, siempre que mantengas el código abierto
- ❌ **No puedes** venderlo ni integrarlo en un producto comercial sin publicar tu código fuente

Si quieres usarlo con fines comerciales (SaaS, producto cerrado, distribución privativa), necesitas una **licencia comercial**. Abre un issue en GitHub con el título "Licencia Comercial" para solicitarla.
