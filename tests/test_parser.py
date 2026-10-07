import os
import pytest
import sys
import runpy
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Add src to path for testing without installing
sys.path.insert(0, str(ROOT / "src"))

from cml_parser import parse_file_safe
from cml_parser import parser as parser_mod
from cml_parser.cml_objects import RelationshipType, SubdomainType

EXAMPLES_DIR = ROOT / "examples"

def get_cml_files():
    cml_files = []
    for root, dirs, files in os.walk(EXAMPLES_DIR):
        for file in files:
            if file.endswith(".cml"):
                cml_files.append(os.path.join(root, file))
    return cml_files

@pytest.mark.parametrize("file_path", get_cml_files())
def test_parse_cml_safe(file_path):
    print(f"Testing {file_path}")
    cml = parse_file_safe(file_path)
    assert cml.parse_results.errors == []
    assert cml.parse_results.ok, f"Parse failed: {cml.parse_results.errors}"


def test_main_without_args(capsys):
    exit_code = parser_mod.main([])
    captured = capsys.readouterr().err
    assert exit_code == 1
    assert "usage:" in captured.lower()


def test_main_with_file(capsys):
    tmp = Path(EXAMPLES_DIR) / "tmp_main_test.cml"
    tmp.write_text("ContextMap Demo {}\n", encoding="utf-8")

    exit_code = parser_mod.main([str(tmp)])
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Successfully parsed" in captured
    tmp.unlink(missing_ok=True)


def test_main_with_bad_file(capsys, tmp_path):
    tmp = tmp_path / "tmp_main_bad.cml"
    tmp.write_text("ContextMap { invalid", encoding="utf-8")
    exit_code = parser_mod.main([str(tmp)])
    captured = capsys.readouterr().err
    assert exit_code == 1
    assert "Error parsing" in captured


def test_module_cli_guard(monkeypatch):
    # Simulate running as a script without args to exercise the __main__ block.
    monkeypatch.setattr(sys, "argv", ["parser.py"])
    # Remove the module to avoid runpy warning about existing entry.
    sys.modules.pop("cml_parser.parser", None)
    importlib.invalidate_caches()
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("cml_parser.parser", run_name="__main__")
    assert excinfo.value.code == 1


def test_parse_file_safe_success():
    from pathlib import Path

    tmp = Path(EXAMPLES_DIR) / "tmp_safe_ok.cml"
    tmp.write_text("ContextMap Demo {}\n", encoding="utf-8")
    cml = parse_file_safe(str(tmp))
    assert cml.parse_results.errors == []
    assert cml.parse_results.ok
    tmp.unlink(missing_ok=True)


def test_parse_file_safe_failure(tmp_path):
    bad_file = tmp_path / "bad.cml"
    bad_file.write_text("ContextMap { invalid", encoding="utf-8")
    cml = parse_file_safe(str(bad_file))
    assert cml.parse_results.model is None
    assert cml.parse_results.errors
    assert "ContextMap" in (cml.parse_results.source or "")


def test_bounded_context_realizes(tmp_path):
    model_file = tmp_path / "bc_realizes.cml"
    model_file.write_text("BoundedContext A implements X realizes Y {}", encoding="utf-8")
    cml = parse_file_safe(str(model_file))
    assert cml.parse_results.errors == []


def test_source_repr_is_clean(tmp_path):
    text = "ContextMap Demo {\n  contains A\n}\n"
    file_path = tmp_path / "demo.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    assert cml.parse_results.source == text


def test_user_story_and_stakeholders(tmp_path):
    content = """
    BoundedContext Demo {}
    UserStory Demo {
        As a "User"
        I want to do "X"
        so that "I achieve Y"
    }
    Stakeholders of Demo {
        StakeholderGroup Team {
            Stakeholder Dev {
                influence HIGH
                interest HIGH
            }
        }
    }
    ValueRegister VR for Demo {
        ValueCluster VC {
            Value Speed {
                Stakeholder Dev {
                    consequences
                        good "faster delivery"
                        action "optimize" ACT
                }
            }
        }
    }
    """
    model_file = tmp_path / "user_story.cml"
    model_file.write_text(content, encoding="utf-8")
    cml = parse_file_safe(str(model_file))
    assert cml.parse_results.errors == []
    assert cml.parse_results.model is not None


def test_relationship_type_filtering(tmp_path):
    text = """
    ContextMap Demo {
        A [ACL]-> B
    }
    BoundedContext A {}
    BoundedContext B {}
    """
    file_path = tmp_path / "rel_filter.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    cm = cml.get_context_map("Demo")
    assert cm is not None
    
    rels = cm.get_relationships_by_type(RelationshipType.ACL)
    assert len(rels) == 1
    assert rels[0].left.name == "A"
    assert rels[0].right.name == "B"


def test_context_subdomain_links(tmp_path):
    text = """
    Domain Demo {
      Subdomain A {}
      Subdomain B {}
    }
    BoundedContext X implements A, B {}
    BoundedContext Y implements B {}
    """
    file_path = tmp_path / "links.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    domain = cml.get_domain("Demo")
    assert domain
    assert len(domain.subdomains) == 2
    
    sd_a = domain.get_subdomain("A")
    sd_b = domain.get_subdomain("B")
    assert sd_a and sd_b
    
    # Check implementations from Subdomain side
    assert len(sd_a.implementations) == 1
    assert sd_a.implementations[0].name == "X"
    
    assert len(sd_b.implementations) == 2
    impl_names = sorted([c.name for c in sd_b.implementations])
    assert impl_names == ["X", "Y"]
    
    ctx_x = sd_a.implementations[0]
    assert ctx_x.name == "X"
    assert len(ctx_x.implements) == 2
    assert ctx_x.get_subdomain("A")
    assert ctx_x.get_subdomain("B")


def test_global_context_queries(tmp_path):
    text = """
    BoundedContext Lonely {}
    BoundedContext WithAgg {
        Aggregate Sales {
            Entity Order {}
        }
    }
    """
    file_path = tmp_path / "queries.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []

    # Context lookup should include contexts not in a map
    lonely = cml.get_context("Lonely")
    with_agg = cml.get_context("WithAgg")
    assert lonely and with_agg
    assert len(cml.contexts) == 2

    # Aggregate and entity lookup through convenience helpers
    agg = cml.get_aggregate("Sales")
    assert agg and agg.name == "Sales"

    ent = cml.get_entity("Order")
    assert ent and ent.name == "Order"

    # Filtered search should return the same entity
    ent_filtered = cml.get_entity("Order", context_name="WithAgg", aggregate_name="Sales")
    assert ent_filtered is ent


def test_domain_subdomain_types(tmp_path):
    text = """
    Domain MyDomain {
        Subdomain Core { type CORE_DOMAIN }
        Subdomain Supp { type SUPPORTING_DOMAIN }
        Subdomain Gen { type GENERIC_SUBDOMAIN }
    }
    """
    file_path = tmp_path / "domain_types.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    domain = cml.get_domain("MyDomain")
    assert domain
    
    # Updated property names
    assert len(domain.core) == 1
    assert domain.core[0].name == "Core"
    
    assert len(domain.supporting) == 1
    assert domain.supporting[0].name == "Supp"
    
    assert len(domain.generic) == 1
    assert domain.generic[0].name == "Gen"


def test_context_aggregates_and_services(tmp_path):
    text = """
    BoundedContext MyContext {
        Aggregate MyAgg {
            Entity MyEntity
        }
        Service MyService {
            void doSomething();
        }
    }
    """
    file_path = tmp_path / "context_children.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    # Find context (it's not in a map, but should be in the object graph if we traverse or if we had a way to get all contexts)
    # Since we don't have a global contexts list in CML (only context_maps), we might need to rely on implementation details or add a global list.
    # Wait, the CML object doesn't have a .contexts list, only .context_maps.
    # But contexts are created. If they are not in a map, they might be orphaned in the CML object unless we add them to a list.
    # The user requirement said: "El ContextMap debería tener ... los contextos (.contexts)".
    # It didn't explicitly say CML should have .contexts.
    # However, for testing, we need to access it.
    # Let's check if the parser adds standalone contexts to anything.
    # Looking at parser.py, standalone contexts are added to `context_map_obj_map` but not to `cml` unless they are in a map.
    # This might be a gap. But for now, let's put it in a map to test it easily.
    
    text_with_map = """
    ContextMap MyMap {
        contains MyContext
    }
    BoundedContext MyContext {
        Aggregate MyAgg {}
        Service MyService {}
    }
    """
    file_path.write_text(text_with_map, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    cm = cml.get_context_map("MyMap")
    assert cm
    ctx = cm.get_context("MyContext")
    assert ctx
    
    assert len(ctx.aggregates) == 1
    assert ctx.aggregates[0].name == "MyAgg"
    assert ctx.get_aggregate("MyAgg")
    
    assert len(ctx.services) == 1
    assert ctx.services[0].name == "MyService"
    assert ctx.get_service("MyService")


def test_object_reprs(tmp_path):
    text = """
    Domain Marketplace {}
    ContextMap MarketplaceMultivendor {
        contains Commerce
    }
    BoundedContext Commerce {}
    """
    file_path = tmp_path / "reprs.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    domain = cml.get_domain("Marketplace")
    assert repr(domain) == "<Domain(Marketplace)>"
    
    cm = cml.get_context_map("MarketplaceMultivendor")
    assert repr(cm) == "<ContextMap(MarketplaceMultivendor)>"
    
    ctx = cm.get_context("Commerce")
    assert repr(ctx) == "<BoundedContext(Commerce)>"
    
    # Check CML repr
    # Note: file path in repr depends on temp file name, so we check partial match or mock it
    cml_repr = repr(cml)
    assert "context_maps=[MarketplaceMultivendor]" in cml_repr
    assert "domains=[Marketplace]" in cml_repr
    assert "file=" in cml_repr

    # Check ParseResult repr
    pr_repr = repr(cml.parse_results)
    assert "<ParseResult OK file=" in pr_repr


def test_parseresult_error_repr(tmp_path):
    bad_file = tmp_path / "bad_repr.cml"
    bad_file.write_text("ContextMap { invalid", encoding="utf-8")
    cml = parse_file_safe(str(bad_file))
    
    pr_repr = repr(cml.parse_results)
    assert "<ParseResult ERROR file=" in pr_repr
    assert "errors=" in pr_repr


def test_subdomain_type_in_body(tmp_path):
    text = """
    Domain MyDomain {
        Subdomain Core {
            type = CORE_DOMAIN
            domainVisionStatement = "Core vision"
        }
        Subdomain Supp {
            type = SUPPORTING_DOMAIN
        }
        Subdomain Gen {
            type = GENERIC_SUBDOMAIN
        }
    }
    """
    file_path = tmp_path / "sd_body.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    domain = cml.get_domain("MyDomain")
    assert domain
    
    assert len(domain.core) == 1
    assert domain.core[0].name == "Core"
    assert domain.core[0].vision == "Core vision"
    
    assert len(domain.supporting) == 1
    assert domain.supporting[0].name == "Supp"
    
    assert len(domain.generic) == 1
    assert domain.generic[0].name == "Gen"


def test_subdomain_entities(tmp_path):
    text = """
    Domain MyDomain {
        Subdomain Core {
            type = CORE_DOMAIN
            Entity Customer {}
            Entity Product {}
        }
    }
    """
    file_path = tmp_path / "sd_entities.cml"
    file_path.write_text(text, encoding="utf-8")
    cml = parse_file_safe(str(file_path))
    assert cml.parse_results.errors == []
    
    domain = cml.get_domain("MyDomain")
    assert domain
    core = domain.core[0]
    assert len(core.entities) == 2
    assert core.get_entity("Customer")
    assert core.get_entity("Product")
