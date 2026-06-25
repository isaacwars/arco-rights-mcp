"""Minimal test suite for ARCO MCP engine."""
import unittest
import json

from arco_mcp.engine import (
    audit_existing_draft, audit_source_provenance,
    build_argument_map, build_timeline,
    draft_arco_request, process_case,
    select_escalation_basis, validate_arco_case,
    # GraphRAG
    LEGAL_GRAPH, _COMMUNITIES, _COMMUNITY_CROSS,
    legal_graph, semantic_search, community_detail,
    # Counter defenses
    counter_defenses, CORPORATE_EVASION_TACTICS,
    # Writing rules
    WRITING_RULES,
)
from arco_mcp.law import ARTICLES, REGULATION_ARTICLES

VALID_CASE = {
    "titular": {"nombre_completo": "Persona Titular", "identificacion": {"tipo":"INE","vigente":True,"se_adjunta_copia":True}},
    "medio_notificaciones": {"tipo":"correo electronico","valor":"a@b.test"},
    "solicitud": {"ciudad":"Puebla, Puebla","fecha":"2026-06-23"},
    "responsable": {"naturaleza":"privado","nombre_legal":"Responsable SA de CV","domicilio":"Domicilio del aviso","canal_arco":"privacidad@example.test",
        "fuente_aviso_privacidad":{"tipo":"URL oficial","referencia":"https://example.test/aviso","fecha_consulta":"2026-06-23","es_fuente_oficial":True}},
    "relacion_juridica": {"tipo":"cliente","descripcion":"Cliente del servicio","folio_contrato_linea_o_cuenta":"123"},
    "datos_personales": [{"descripcion":"CURP","categoria":"identificacion","sensible":False}],
    "derechos_solicitados": [{"tipo":"acceso","peticion_concreta":"Conocer datos personales"}],
    "anexos": ["INE"],
}

class EngineTest(unittest.TestCase):
    def test_validate_ready_case(self):
        result = validate_arco_case(VALID_CASE)
        self.assertTrue(result["ready_to_draft"])

    def test_blocks_missing_legal_entity(self):
        case = json.loads(json.dumps(VALID_CASE))
        case["responsable"]["nombre_legal"] = ""
        result = validate_arco_case(case)
        self.assertFalse(result["ready_to_draft"])

    def test_blocks_placeholders(self):
        case = json.loads(json.dumps(VALID_CASE))
        case["responsable"]["nombre_legal"] = "RAZON SOCIAL EXACTA"
        result = validate_arco_case(case)
        self.assertFalse(result["ready_to_draft"])

    def test_blocks_wrong_legal_regime(self):
        case = json.loads(json.dumps(VALID_CASE))
        case["responsable"]["naturaleza"] = "sujeto_obligado"
        result = validate_arco_case(case)
        codes = {blocker["code"] for blocker in result["blockers"]}
        self.assertIn("wrong_legal_regime", codes)

    def test_blocks_sensitive_categories_not_marked(self):
        case = json.loads(json.dumps(VALID_CASE))
        case["datos_personales"] = [{"descripcion":"historial clinico","categoria":"salud","sensible":False}]
        result = validate_arco_case(case)
        self.assertFalse(result["ready_to_draft"])

    def test_process_case_ready(self):
        result = process_case(json.loads(json.dumps(VALID_CASE)))
        self.assertTrue(result["ok"])
        self.assertTrue(result["ready_to_draft"])
        self.assertIsNotNone(result["draft"])

    def test_process_case_blocked(self):
        case = json.loads(json.dumps(VALID_CASE))
        case["responsable"]["nombre_legal"] = ""
        result = process_case(case)
        self.assertFalse(result["ready_to_draft"])
        self.assertIsNone(result["draft"])
        self.assertIsNotNone(result["draft_preview"])

    def test_timeline_business_days(self):
        result = build_timeline("2026-06-23")
        self.assertEqual(result["limite_respuesta_20_dias_habiles"], "2026-07-21")

    def test_audit_flags_bad_draft(self):
        result = audit_existing_draft("El INAI e IFAI-PRODATOS impondran multa automatica en dias naturales.")
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("wrong_authority", codes)
        self.assertIn("obsolete_procedure_or_authority", codes)

    def test_escalation_basis(self):
        result = select_escalation_basis("amparo")
        self.assertTrue(result["ok"])
        self.assertIn("amparo", result)
        self.assertIn("constitucion", result)


# ═══════════════════════════════════════════════════════════════════════
# GRAPH RAG TEST SUITE — 65 tests
# ═══════════════════════════════════════════════════════════════════════

class GraphRAGCommunitiesTest(unittest.TestCase):
    """Structural integrity of communities."""

    def test_all_12_communities_exist(self):
        self.assertEqual(len(_COMMUNITIES), 12)

    def test_every_community_has_required_keys(self):
        required = {"id", "title", "description", "nodes", "instrumentos"}
        for cid, cdata in _COMMUNITIES.items():
            self.assertTrue(
                required.issubset(set(cdata.keys())),
                f"Community {cid} missing keys: {required - set(cdata.keys())}"
            )

    def test_community_id_matches_key(self):
        for cid, cdata in _COMMUNITIES.items():
            self.assertEqual(cid, cdata["id"],
                             f"Key {cid} ≠ cdata['id'] {cdata['id']}")

    def test_no_duplicate_nodes_across_communities(self):
        node_to_cid: dict[str, str] = {}
        for cid, cdata in _COMMUNITIES.items():
            for node in cdata["nodes"]:
                if node in node_to_cid:
                    self.fail(
                        f"Node {node} appears in both {cid} and {node_to_cid[node]}"
                    )
                node_to_cid[node] = cid

    def test_total_nodes_across_all_communities(self):
        total = sum(len(c["nodes"]) for c in _COMMUNITIES.values())
        self.assertEqual(total, 90, f"Expected 90 total node placements, got {total}")

    def test_every_node_in_communities_is_resolvable(self):
        """Every node in communities must exist in ARTICLES, REGULATION_ARTICLES,
        WRITING_RULES, or be resolvable to CONSTITUTION/LFPA/AMPARO."""
        from arco_mcp.escalation import CONSTITUTION_ARTICLES, LFPA_ARTICLES, AMPARO_ARTICLES
        for cid, cdata in _COMMUNITIES.items():
            for node in cdata["nodes"]:
                resolved = (
                    node in ARTICLES
                    or node in REGULATION_ARTICLES
                    or node in WRITING_RULES
                    or (node.startswith("CPEUM-") and node.replace("CPEUM-", "") in CONSTITUTION_ARTICLES)
                    or (node.startswith("LFPA-") and node.replace("LFPA-", "") in LFPA_ARTICLES)
                    or (node.startswith("LA-") and node.replace("LA-", "") in AMPARO_ARTICLES)
                )
                self.assertTrue(resolved, f"Node {node} in {cid} is not resolvable")

    def test_every_community_has_nodes(self):
        for cid, cdata in _COMMUNITIES.items():
            self.assertGreater(len(cdata["nodes"]), 0,
                               f"Community {cid} has no nodes")

    def test_every_community_has_description(self):
        for cid, cdata in _COMMUNITIES.items():
            self.assertGreater(len(cdata["description"]), 10,
                               f"Community {cid} has too short description")

    def test_instrumentos_field_is_valid(self):
        valid = {"LFPDPPP 2025", "Reglamento LFPDPPP 2011", "CPEUM", "LFPA", "Ley de Amparo", "Guia de Redaccion"}
        for cid, cdata in _COMMUNITIES.items():
            for inst in cdata["instrumentos"]:
                self.assertIn(inst, valid,
                              f"Community {cid} has unknown instrumento: {inst}")


class GraphRAGRelationshipsTest(unittest.TestCase):
    """Integrity of the LEGAL_GRAPH relationships."""

    def test_every_source_in_legal_graph_is_resolvable(self):
        for src in LEGAL_GRAPH:
            resolved = (
                src in ARTICLES
                or src in REGULATION_ARTICLES
                or src.startswith("CPEUM-")
                or src.startswith("LFPA-")
                or src.startswith("LA-")
            )
            self.assertTrue(resolved, f"Source node {src} not resolvable")

    def test_every_target_in_legal_graph_is_resolvable(self):
        from arco_mcp.escalation import CONSTITUTION_ARTICLES, LFPA_ARTICLES, AMPARO_ARTICLES
        all_known = set(ARTICLES.keys()) | set(REGULATION_ARTICLES.keys())
        all_known |= {"CPEUM-" + k for k in CONSTITUTION_ARTICLES}
        all_known |= {"LFPA-" + k for k in LFPA_ARTICLES}
        all_known |= {"LA-" + k for k in AMPARO_ARTICLES}
        for src, rels in LEGAL_GRAPH.items():
            for rel in rels:
                self.assertIn(rel["target"], all_known,
                              f"{src} → {rel['target']}: target not resolvable")

    def test_all_relationships_have_valid_type(self):
        valid = {"requires", "limits", "overrides", "complements",
                 "excepts", "procedural", "defines"}
        for src, rels in LEGAL_GRAPH.items():
            for rel in rels:
                self.assertIn(rel["type"], valid,
                              f"{src} → {rel['target']}: invalid type '{rel['type']}'")

    def test_all_relationships_have_reason(self):
        for src, rels in LEGAL_GRAPH.items():
            for rel in rels:
                self.assertGreater(len(rel.get("reason", "")), 5,
                                   f"{src} → {rel['target']}: reason too short or missing")

    def test_no_self_references(self):
        for src, rels in LEGAL_GRAPH.items():
            for rel in rels:
                self.assertNotEqual(src, rel["target"],
                                    f"Self-reference: {src} → {rel['target']}")

    def test_cross_community_graph_built(self):
        self.assertGreater(len(_COMMUNITY_CROSS), 0)
        # Every community should have at least one cross-reference
        for cid in _COMMUNITIES:
            self.assertIn(cid, _COMMUNITY_CROSS, f"Community {cid} missing from cross graph")


class LegalGraphToolTest(unittest.TestCase):
    """legal_graph() function tests."""

    def test_single_article(self):
        r = legal_graph(["26"])
        self.assertTrue(r["ok"])
        self.assertIn("26", r["relationships_forward"])
        self.assertIn("articles_to_lookup", r)

    def test_multiple_articles(self):
        r = legal_graph(["26", "36"])
        self.assertTrue(r["ok"])
        self.assertIn("26", r["relationships_forward"])
        self.assertIn("36", r["relationships_forward"])

    def test_returns_articles_to_lookup(self):
        r = legal_graph(["26"])
        ids = r["articles_to_lookup"]
        self.assertIn("28", ids)
        self.assertIn("31", ids)

    def test_unknown_article_returns_empty(self):
        r = legal_graph(["999"])
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["relationships_forward"]), 0)

    def test_cpeum_article(self):
        r = legal_graph(["CPEUM-16"])
        self.assertTrue(r["ok"])
        self.assertIn("CPEUM-16", r["relationships_forward"])

    def test_lfpa_article(self):
        r = legal_graph(["LFPA-35"])
        self.assertTrue(r["ok"])
        self.assertIn("LFPA-35", r["relationships_forward"])

    def test_la_article(self):
        r = legal_graph(["LA-17"])
        self.assertTrue(r["ok"])
        self.assertIn("LA-17", r["relationships_forward"])

    def test_regulation_article(self):
        r = legal_graph(["R69"])
        self.assertTrue(r["ok"])
        self.assertIn("R69", r["relationships_forward"])

    def test_graphto_lawarticles_flow(self):
        """legal_graph → article_bundle roundtrip for all instruments."""
        from arco_mcp.engine import article_bundle
        # Test multi-instrument resolution
        r = legal_graph(["CPEUM-16", "26", "LA-17", "LFPA-35", "R69"])
        ids = r["articles_to_lookup"]
        bundle = article_bundle(ids)
        self.assertGreater(len(bundle["articles"]), 0)
        instruments_found = {a.get("instrumento") for a in bundle["articles"].values()}
        self.assertIn("LFPDPPP 2025", instruments_found)
        self.assertIn("CPEUM", instruments_found)


class SemanticSearchTest(unittest.TestCase):
    """semantic_search() function tests."""

    def test_empty_query(self):
        r = semantic_search("")
        self.assertTrue(r["ok"])
        self.assertEqual(r["communities_found"], 0)

    def test_oposicion_query(self):
        r = semantic_search("oponerme a transferencia de datos a empresas afiliadas")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_acceso_query(self):
        r = semantic_search("quiero acceder a mis datos personales que tiene la empresa")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_rectificacion_query(self):
        r = semantic_search("necesito corregir mi nombre en sus registros")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_cancelacion_query(self):
        r = semantic_search("cancelar todos mis datos personales de su base")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_amparo_query(self):
        r = semantic_search("amparo contra resolucion de la secretaria anticorrupcion")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_sanciones_query(self):
        r = semantic_search("multas por no responder mi solicitud ARCO")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_consentimiento_query(self):
        r = semantic_search("no di mi consentimiento para que usen mis datos")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_query_with_accents(self):
        r = semantic_search("oposición a transferéncia de datos")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_query_returns_matching_articles(self):
        r = semantic_search("oponerme a transferencia")
        for c in r["top_communities"]:
            self.assertIn("matching_articles", c)

    def test_query_returns_instrumentos(self):
        r = semantic_search("sanciones")
        for c in r["top_communities"]:
            self.assertIn("instrumentos", c)
            self.assertIsInstance(c["instrumentos"], list)

    def test_query_returns_suggested_next_communities(self):
        r = semantic_search("transferencia de datos")
        self.assertIn("suggested_next_communities", r)

    def test_query_returns_must_use_tools(self):
        r = semantic_search("consentimiento")
        self.assertIn("community_detail", r["must_use_tools"])


class CommunityDetailTest(unittest.TestCase):
    """community_detail() function tests."""

    def test_valid_community(self):
        cd = community_detail("c_transfers")
        self.assertTrue(cd["ok"])

    def test_invalid_community(self):
        cd = community_detail("nonexistent")
        self.assertFalse(cd["ok"])
        self.assertIn("error", cd)

    def test_community_has_articles(self):
        cd = community_detail("c_arco_rights")
        self.assertGreater(len(cd["articles"]), 0)

    def test_community_has_internal_relationships(self):
        cd = community_detail("c_transfers")
        self.assertGreater(len(cd["internal_relationships"]), 0)

    def test_community_has_external_connections(self):
        cd = community_detail("c_transfers")
        self.assertGreater(len(cd["external_connections"]), 0)

    def test_community_has_summary(self):
        cd = community_detail("c_amparo")
        self.assertGreater(len(cd["summary"]), 50)

    def test_community_has_title(self):
        cd = community_detail("c_sanctions")
        self.assertGreater(len(cd["title"]), 5)

    def test_community_has_instrumentos(self):
        cd = community_detail("c_general")
        self.assertIn("LFPDPPP 2025", cd["instrumentos"])
        self.assertIn("CPEUM", cd["instrumentos"])

    def test_all_12_communities_return_ok(self):
        for cid in _COMMUNITIES:
            cd = community_detail(cid)
            self.assertTrue(cd["ok"], f"Community {cid} failed: {cd.get('error', '')}")

    def test_community_has_cross_stats(self):
        cd = community_detail("c_consent")
        self.assertIn("cross_community_stats", cd)


class CounterDefensesIntegrationTest(unittest.TestCase):
    """counter_defenses integration with the graph and articles."""

    def test_all_tactics_have_valid_articles(self):
        for t in CORPORATE_EVASION_TACTICS:
            for art_ref in t["contra_articulos"]:
                normalized = art_ref.replace("art. ", "").split(" ")[0].split("-")[0].strip()
                resolved = normalized in ARTICLES or normalized in REGULATION_ARTICLES
                self.assertTrue(resolved,
                    f"Tactic {t['id']}: article ref '{art_ref}' (→ '{normalized}') not found")

    def test_oposicion_case_includes_transfer_defenses(self):
        import json
        case = json.dumps({"derechos_solicitados": [{"tipo": "oposicion"}]})
        r = counter_defenses(case)
        ids = [d["id"] for d in r["defensas"]]
        self.assertIn("affiliate_transfer_exception", ids)
        self.assertIn("legitimate_interest", ids)

    def test_acceso_case_excludes_transfer_defenses(self):
        import json
        case = json.dumps({"derechos_solicitados": [{"tipo": "acceso"}]})
        r = counter_defenses(case)
        ids = [d["id"] for d in r["defensas"]]
        self.assertNotIn("affiliate_transfer_exception", ids)

    def test_every_defense_has_articulos_completos(self):
        import json
        case = json.dumps({"derechos_solicitados": [
            {"tipo": "oposicion"}, {"tipo": "cancelacion"}, {"tipo": "acceso"}
        ]})
        r = counter_defenses(case)
        for d in r["defensas"]:
            self.assertGreater(len(d.get("articulos_completos", [])), 0,
                               f"Defense {d['id']} has no articulos_completos")

    def test_every_defense_has_fundamento(self):
        import json
        case = json.dumps({"derechos_solicitados": [{"tipo": "oposicion"}]})
        r = counter_defenses(case)
        for d in r["defensas"]:
            self.assertGreater(len(d.get("fundamento_destructivo", "")), 20,
                               f"Defense {d['id']} has too short fundamento")


class ArticleBundleTest(unittest.TestCase):
    """article_bundle() multi-instrument resolution."""

    def test_lfpdppp_only(self):
        from arco_mcp.engine import article_bundle
        b = article_bundle(["1", "28", "31"])
        self.assertEqual(len(b["articles"]), 3)
        for a in b["articles"].values():
            self.assertEqual(a["instrumento"], "LFPDPPP 2025")

    def test_multi_instrument(self):
        from arco_mcp.engine import article_bundle
        b = article_bundle(["1", "R69", "CPEUM-16", "LA-17", "LFPA-35"])
        self.assertEqual(len(b["articles"]), 5)
        insts = {a["instrumento"] for a in b["articles"].values()}
        self.assertIn("LFPDPPP 2025", insts)
        self.assertIn("Reglamento LFPDPPP 2011", insts)
        self.assertIn("CPEUM", insts)
        self.assertIn("Ley de Amparo", insts)
        self.assertIn("LFPA", insts)

    def test_unknown_id_skipped(self):
        from arco_mcp.engine import article_bundle
        b = article_bundle(["1", "999", "R999"])
        self.assertEqual(len(b["articles"]), 1)


class GraphRAGEdgeCaseTest(unittest.TestCase):
    """Edge cases and robustness."""

    def test_community_summary_includes_all_nodes(self):
        for cid in _COMMUNITIES:
            cd = community_detail(cid)
            self.assertEqual(cd["node_count"], len(_COMMUNITIES[cid]["nodes"]),
                             f"Community {cid}: node count mismatch")

    def test_semantic_search_single_token(self):
        r = semantic_search("oposicion")
        self.assertTrue(r["ok"])

    def test_semantic_search_long_query(self):
        r = semantic_search(
            "necesito ejercer mi derecho de oposicion porque la empresa esta "
            "transfiriendo mis datos personales a terceros sin mi consentimiento "
            "y ademas no me han respondido en el plazo legal de 20 dias"
        )
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["top_communities"]), 1)

    def test_legal_graph_backward_relationships(self):
        """legal_graph returns backward relationships (who points TO the queried article)."""
        r = legal_graph(["28"])
        # art 28 should be referenced by many articles
        self.assertIn("relationships_backward", r)

    def test_counter_defenses_must_use_tools(self):
        import json
        case = json.dumps({"derechos_solicitados": [{"tipo": "oposicion"}]})
        r = counter_defenses(case)
        self.assertIn("must_use_tools", r)
        self.assertIn("audit_draft", r["must_use_tools"])

    def test_semantic_search_must_use_tools(self):
        r = semantic_search("transferencia")
        self.assertIn("community_detail", r["must_use_tools"])
        self.assertIn("law_articles", r["must_use_tools"])


if __name__ == "__main__":
    unittest.main()
