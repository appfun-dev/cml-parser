import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cml_parser import parse_text


def test_leading_comment_attached_to_bounded_context():
    cml = parse_text("""
// Customer management context
// second line
BoundedContext CustomerContext {
}
""")
    ctx = cml.get_context("CustomerContext")
    assert ctx.leading_comment == "Customer management context\nsecond line"


def test_leading_comment_broken_by_blank_line():
    cml = parse_text("""
// detached comment

BoundedContext CustomerContext {
}
""")
    ctx = cml.get_context("CustomerContext")
    assert ctx.leading_comment is None


def test_inner_first_comment_paragraph():
    cml = parse_text("""
BoundedContext CustomerContext {
    // inner first
    // inner second

    // not part of first paragraph
    Aggregate Customers {
    }
}
""")
    ctx = cml.get_context("CustomerContext")
    assert ctx.inner_comment == "inner first\ninner second"


def test_block_comment_support():
    cml = parse_text("""
/* block doc
 * more doc
 */
BoundedContext CustomerContext {
    /* inner block */
    Aggregate Customers {
    }
}
""")
    ctx = cml.get_context("CustomerContext")
    assert ctx.leading_comment == "block doc\nmore doc"
    assert ctx.inner_comment == "inner block"


def test_entity_leading_comment_inside_aggregate():
    cml = parse_text("""
BoundedContext CustomerContext {
    Aggregate Customers {
        // the customer entity
        Entity Customer {
            String name
        }
    }
}
""")
    ent = cml.get_entity("Customer")
    assert ent.leading_comment == "the customer entity"
    agg = cml.get_aggregate("Customers")
    assert agg.inner_comment == "the customer entity"


def test_trailing_comment_not_treated_as_leading():
    cml = parse_text("""
BoundedContext A { } // trailing note
BoundedContext B { }
""")
    assert cml.get_context("B").leading_comment is None


def test_tag_extraction_single_line_multiple_tags():
    cml = parse_text("""
// @stakeholder:ProspectiveCustomer @value:Privacy
// @userstory:ManageCustomers @actor:InsuranceEmployee
BoundedContext CustomerContext {
}
""")
    ctx = cml.get_context("CustomerContext")
    assert ctx._doc_tags == {
        "stakeholder": ["ProspectiveCustomer"],
        "value": ["Privacy"],
        "userstory": ["ManageCustomers"],
        "actor": ["InsuranceEmployee"],
    }
    assert ctx.get_tag("actor") == "InsuranceEmployee"
    assert ctx.get_tags("value") == ["Privacy"]
    assert ctx.get_tag("missing") is None
    assert ctx.has_tag("actor", "InsuranceEmployee")
    assert not ctx.has_tag("actor", "SomeoneElse")
    assert not ctx.has_tag("missing", "x")
    assert ctx.has_tags({"stakeholder": "ProspectiveCustomer", "value": "Privacy"})
    assert not ctx.has_tags({"stakeholder": "ProspectiveCustomer", "value": "Nope"})
    assert ctx.has_tags({})


def test_tags_from_inner_comment_and_duplicates():
    cml = parse_text("""
BoundedContext CustomerContext {
    // @team:Sales @value:Privacy @value:Security
    Aggregate Customers {
    }
}
""")
    ctx = cml.get_context("CustomerContext")
    assert ctx._doc_tags["team"] == ["Sales"]
    assert ctx._doc_tags["value"] == ["Privacy", "Security"]


def test_tags_on_entity_and_service():
    cml = parse_text("""
BoundedContext Shop {
    Aggregate Catalog {
        // @ddd:entity
        Entity Product {
            String name
        }
    }
    // @layer:application
    Service CheckoutService {
        void checkout();
    }
}
""")
    ctx = cml.get_context("Shop")
    ent = ctx.aggregates[0].get_entity("Product") if ctx.aggregates else None
    assert ent is not None
    assert ent._doc_tags["ddd"] == ["entity"]
    svc = ctx.get_service("CheckoutService")
    assert svc.leading_comment == "@layer:application"
    assert svc.get_tag("layer") == "application"


def test_top_level_use_case_with_comment_and_tags():
    # Regression: top-level 'UseCase X {}' was swallowed by the grammar's
    # scUseCase alternative and never reached cml.use_cases
    cml = parse_text("""
// @stakeholder:employee
UseCase ManageEmployees {
}
""")
    uc = cml.get_use_case("ManageEmployees")
    assert uc is not None
    assert uc.leading_comment == "@stakeholder:employee"
    assert uc.has_tag("stakeholder", "employee")


def test_service_cutter_use_case_still_parsed_as_sc():
    cml = parse_text("""
UseCase SC {
    isLatencyCritical = true
    reads "a"
}
""")
    assert cml.use_cases == []
    assert cml.service_cutter is not None
    assert cml.service_cutter.use_cases[0].name == "SC"


def test_subdomain_after_vision_statement_parsed():
    # Regression: rawStatement swallowed the Subdomain keyword after a
    # vision statement inside a Domain body
    cml = parse_text("""
Domain HR {
    vision = "v"
    // @stakeholder:manager
    Subdomain People { type CORE_DOMAIN }
}
""")
    domain = cml.get_domain("HR")
    sd = domain.get_subdomain("People")
    assert sd is not None
    assert sd.leading_comment == "@stakeholder:manager"
    assert sd.has_tag("stakeholder", "manager")


def test_find_tagged_searches_all_object_types():
    cml = parse_text("""
// @stakeholder:employee
Domain HR {
    // @stakeholder:manager
    Subdomain People { type CORE_DOMAIN }
}

BoundedContext CustomerContext {
    // @stakeholder:employee
    Aggregate Customers {
        // @stakeholder:customer
        Entity Customer {
            String name
        }
        // @stakeholder:employee
        Entity Employee {
            String email
        }
    }
    // @stakeholder:employee
    Service HrService {
        void onboard();
    }
}
""")
    results = cml.find_tagged("stakeholder", "employee")
    kinds_names = {(kind, obj.name) for kind, obj in results}
    assert ("Domain", "HR") in kinds_names
    assert ("Aggregate", "Customers") in kinds_names
    assert ("Entity", "Employee") in kinds_names
    assert ("Service", "HrService") in kinds_names
    assert ("Context", "CustomerContext") in kinds_names  # via inner comment
    assert ("Entity", "Customer") not in kinds_names

    # key-only search matches regardless of value
    all_stakeholders = cml.find_tagged("stakeholder")
    names = {obj.name for _, obj in all_stakeholders}
    assert {"HR", "People", "Customers", "Customer", "Employee", "HrService"} <= names


def test_object_without_comments_has_empty_tags():
    cml = parse_text("""
BoundedContext Plain {
    Aggregate Orders {
        Entity Order {
            String id
        }
    }
}
""")
    ctx = cml.get_context("Plain")
    assert ctx.leading_comment is None
    assert ctx.inner_comment is None
    assert ctx._doc_tags == {}
