import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cml_parser import parse_text
from cml_parser.cli import main
from cml_parser.tag_filter import TagExpressionError, evaluate


TAGGED_CML = """
// @stakeholder:employee @domain:hr
BoundedContext HrContext {
    // @stakeholder:employee
    Aggregate Employees {
        // core employee data

        // @stakeholder:employee @pii:true
        Entity Employee {
            String email
        }
        // @deprecated:true
        Entity LegacyRecord {
            String note
        }
    }
}

// @stakeholder:customer
BoundedContext CustomerContext {
    Aggregate Customers {
        Entity Customer {
            String name
        }
    }
}

// untagged context
BoundedContext PlainContext {
    Aggregate Stuff {
        Entity Thing {
            String id
        }
    }
}
"""


def test_evaluate_single_tag_with_value():
    tags = {"stakeholder": ["employee"]}
    assert evaluate("@stakeholder:employee", tags)
    assert not evaluate("@stakeholder:customer", tags)


def test_evaluate_key_only_matches_any_value():
    tags = {"stakeholder": ["employee", "customer"]}
    assert evaluate("@stakeholder", tags)
    assert not evaluate("@missing", tags)


def test_evaluate_not_and_or():
    tags = {"a": ["1"], "b": ["2"]}
    assert evaluate("@a and @b", tags)
    assert not evaluate("@a and @c", tags)
    assert evaluate("@a or @c", tags)
    assert evaluate("not @c", tags)
    assert not evaluate("not @a", tags)


def test_evaluate_parentheses_and_precedence():
    tags = {"a": ["1"], "c": ["3"]}
    assert evaluate("(@a or @b) and not @d", tags)
    assert evaluate("@a and @c or @d", tags)  # and binds tighter than or
    assert evaluate("@a and (@c or @d)", tags)
    assert not evaluate("@a and (@b or @d)", tags)


def test_evaluate_keywords_case_insensitive():
    tags = {"a": ["1"]}
    assert evaluate("@a AND NOT @b", tags)
    assert evaluate("@a Or @b", tags)


def test_parse_errors():
    with pytest.raises(TagExpressionError):
        evaluate("", {})
    with pytest.raises(TagExpressionError):
        evaluate("@a and", {})
    with pytest.raises(TagExpressionError):
        evaluate("(@a", {})
    with pytest.raises(TagExpressionError):
        evaluate("foo", {})
    with pytest.raises(TagExpressionError):
        evaluate("@a @b", {})


def test_commented_matches_tags():
    cml = parse_text(TAGGED_CML)
    emp = cml.get_entity("Employee", context_name="HrContext")
    assert emp.matches_tags("@stakeholder:employee and @pii")
    assert not emp.matches_tags("@stakeholder:customer")
    assert emp.matches_tags("not @deprecated")


def test_find_by_tags_expression():
    cml = parse_text(TAGGED_CML)
    results = cml.find_by_tags("@stakeholder and not @deprecated:true")
    kinds_names = {(k, o.name) for k, o in results}
    assert ("Context", "HrContext") in kinds_names
    assert ("Entity", "Employee") in kinds_names
    assert ("Context", "CustomerContext") in kinds_names
    assert ("Entity", "LegacyRecord") not in kinds_names


def test_filter_by_tags_keeps_matching_subtrees():
    cml = parse_text(TAGGED_CML)
    filtered = cml.filter_by_tags("@stakeholder:employee")
    ctx_names = [c.name for c in filtered.contexts]
    assert "HrContext" in ctx_names
    assert "CustomerContext" not in ctx_names
    assert "PlainContext" not in ctx_names

    # HrContext matches itself -> whole subtree kept
    hr = filtered.get_context("HrContext")
    agg = hr.get_aggregate("Employees")
    assert [e.name for e in agg.entities] == ["Employee", "LegacyRecord"]


def test_filter_by_tags_matching_object_keeps_all_descendants():
    cml = parse_text(TAGGED_CML)
    # CustomerContext matches itself -> whole subtree kept, including
    # untagged children
    filtered = cml.filter_by_tags("@stakeholder:customer")
    ctx = filtered.get_context("CustomerContext")
    assert ctx is not None
    agg = ctx.get_aggregate("Customers")
    assert [e.name for e in agg.entities] == ["Customer"]


def test_filter_by_tags_prunes_non_matching_siblings():
    cml = parse_text(TAGGED_CML)
    # only the Employee entity matches (@pii:true); context and aggregate
    # are kept as ancestors, LegacyRecord is pruned
    filtered = cml.filter_by_tags("@pii:true")
    hr = filtered.get_context("HrContext")
    assert hr is not None
    agg = hr.get_aggregate("Employees")
    assert [e.name for e in agg.entities] == ["Employee"]


def test_cli_generate_with_tags_filter(tmp_path, capsys):
    cml_file = tmp_path / "tagged.cml"
    cml_file.write_text(TAGGED_CML)
    out = tmp_path / "out"
    rc = main([
        "generate", "-i", str(cml_file), "-g", "mermaid",
        "-o", str(out), "--tags", "@pii:true",
    ])
    assert rc == 0
    assert (out / "HrContext.mmd").exists()
    assert not (out / "CustomerContext.mmd").exists()
    assert not (out / "PlainContext.mmd").exists()
    content = (out / "HrContext.mmd").read_text()
    assert "class Employee" in content
    assert "LegacyRecord" not in content


def test_cli_generate_with_invalid_tags_expression(tmp_path, capsys):
    cml_file = tmp_path / "tagged.cml"
    cml_file.write_text(TAGGED_CML)
    rc = main([
        "generate", "-i", str(cml_file), "-g", "mermaid",
        "-o", str(tmp_path / "out"), "--tags", "@a and",
    ])
    assert rc == 1
    assert "Invalid --tags expression" in capsys.readouterr().err


def test_cli_generate_tags_with_generic_template(tmp_path):
    cml_file = tmp_path / "tagged.cml"
    cml_file.write_text(TAGGED_CML)
    tpl = tmp_path / "ctx.j2"
    tpl.write_text("{% for ctx in model.contexts %}{{ ctx.name }} {% endfor %}")
    out = tmp_path / "out"
    rc = main([
        "generate", "-i", str(cml_file), "-g", "generic",
        "-t", str(tpl), "-o", str(out), "-f", "ctx.txt",
        "--tags", "(@stakeholder:employee or @stakeholder:customer) and not @deprecated:true",
    ])
    assert rc == 0
    assert (out / "ctx.txt").read_text() == "HrContext CustomerContext "
