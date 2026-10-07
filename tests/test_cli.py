import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cml_parser.cli import main


SAMPLE = """
ContextMap ShopMap {
    contains Sales, Shipping
    Sales [D] <- [U] Shipping
}

// Sales context @team:Sales
BoundedContext Sales {
    Aggregate Orders {
        Entity Order {
            aggregateRoot
            - Customer customer
            String status
        }
        Entity Customer {
            String name
        }
        enum OrderState {
            NEW, PAID
        }
        Service OrderService {
            void placeOrder(@Order order);
        }
    }
}

BoundedContext Shipping {
    Aggregate Delivery {
        Entity Shipment {
            aggregateRoot
            String address
        }
    }
}
"""


def _write_sample(tmp_path: Path) -> Path:
    path = tmp_path / "sample.cml"
    path.write_text(SAMPLE)
    return path


def test_validate_ok(tmp_path, capsys):
    cml = _write_sample(tmp_path)
    assert main(["validate", "-i", str(cml)]) == 0
    assert "is valid" in capsys.readouterr().out


def test_validate_invalid(tmp_path, capsys):
    bad = tmp_path / "bad.cml"
    bad.write_text("BoundedContext {")
    assert main(["validate", "-i", str(bad)]) == 1
    assert "Validation failed" in capsys.readouterr().err


def test_validate_missing_file(tmp_path, capsys):
    assert main(["validate", "-i", str(tmp_path / "nope.cml")]) == 1
    assert "not found" in capsys.readouterr().err


def test_generate_mermaid(tmp_path):
    cml = _write_sample(tmp_path)
    out = tmp_path / "out"
    assert main(["generate", "-i", str(cml), "-g", "mermaid", "-o", str(out)]) == 0

    sales = (out / "Sales.mmd").read_text()
    assert sales.startswith("classDiagram")
    assert "namespace Orders" in sales
    assert "class Order" in sales
    assert "<<Aggregate Root>>" in sales
    assert "+String status" in sales
    assert "<<Enumeration>>" in sales
    assert "NEW" in sales
    assert "Order --> Customer" in sales
    assert "<<Service>>" in sales
    assert "placeOrder(Order order)" in sales

    shipping = (out / "Shipping.mmd").read_text()
    assert "class Shipment" in shipping

    cmap = (out / "ShopMap_context_map.mmd").read_text()
    assert cmap.startswith("flowchart LR")
    assert "Sales[Sales]" in cmap
    assert "Shipping[Shipping]" in cmap
    # arrow drawn from upstream (Shipping) to downstream (Sales)
    assert 'Shipping -->|"Downstream-Upstream' in cmap


def test_generate_plantuml(tmp_path):
    cml = _write_sample(tmp_path)
    out = tmp_path / "out"
    assert main(["generate", "-i", str(cml), "-g", "plantuml", "-o", str(out)]) == 0

    sales = (out / "Sales.puml").read_text()
    assert sales.startswith("@startuml")
    assert sales.rstrip().endswith("@enduml")
    assert 'package "Orders" <<Rectangle>>' in sales
    assert "class Order <<Aggregate Root>>" in sales
    assert "+status : String" in sales
    assert "enum OrderState" in sales
    assert "NEW" in sales
    assert "Order --> Customer" in sales
    assert "class OrderService <<Service>>" in sales
    assert "placeOrder(order : Order) : void" in sales

    shipping = (out / "Shipping.puml").read_text()
    assert "class Shipment <<Aggregate Root>>" in shipping

    cmap = (out / "ShopMap_context_map.puml").read_text()
    assert cmap.startswith("@startuml")
    assert "[Sales]" in cmap
    assert "[Shipping]" in cmap
    assert "[Shipping] --> [Sales] : Downstream-Upstream" in cmap


def test_generate_mermaid_invalid_input(tmp_path, capsys):
    bad = tmp_path / "bad.cml"
    bad.write_text("BoundedContext {")
    assert main(["generate", "-i", str(bad), "-g", "mermaid", "-o", str(tmp_path / "out")]) == 1
    assert "Cannot generate" in capsys.readouterr().err


def test_generate_generic_jinja2(tmp_path):
    cml = _write_sample(tmp_path)
    tpl = tmp_path / "glossary.md.j2"
    tpl.write_text(
        "{% for ctx in model.contexts %}"
        "{{ ctx.name }}:{% for agg in ctx.aggregates %} {{ agg.name }};{% endfor %}\n"
        "{% endfor %}"
    )
    out = tmp_path / "out"
    rc = main([
        "generate", "-i", str(cml), "-g", "generic",
        "-t", str(tpl), "-o", str(out), "-f", "glossary.md",
    ])
    assert rc == 0
    content = (out / "glossary.md").read_text()
    assert "Sales: Orders;" in content
    assert "Shipping: Delivery;" in content


def test_generate_generic_template_accesses_comments_and_tags(tmp_path):
    cml = _write_sample(tmp_path)
    tpl = tmp_path / "doc.j2"
    tpl.write_text(
        "{% for ctx in model.contexts if ctx.leading_comment %}"
        "{{ ctx.name }} // {{ ctx.leading_comment }} team={{ ctx.get_tag('team') }}\n"
        "{% endfor %}"
    )
    out = tmp_path / "out"
    rc = main(["generate", "-i", str(cml), "-g", "generic", "-t", str(tpl), "-o", str(out), "-f", "doc.txt"])
    assert rc == 0
    assert "Sales // Sales context @team:Sales team=Sales" in (out / "doc.txt").read_text()


def test_generate_generic_requires_template(tmp_path, capsys):
    cml = _write_sample(tmp_path)
    rc = main(["generate", "-i", str(cml), "-g", "generic", "-o", str(tmp_path / "out")])
    assert rc == 1
    assert "requires a template" in capsys.readouterr().err


def test_generate_generic_template_not_found(tmp_path, capsys):
    cml = _write_sample(tmp_path)
    rc = main([
        "generate", "-i", str(cml), "-g", "generic",
        "-t", str(tmp_path / "missing.j2"), "-o", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "Template not found" in capsys.readouterr().err


def test_generate_generic_default_output_name(tmp_path):
    cml = _write_sample(tmp_path)
    tpl = tmp_path / "report.j2"
    tpl.write_text("contexts: {{ model.contexts | length }}")
    out = tmp_path / "out"
    rc = main(["generate", "-i", str(cml), "-g", "generic", "-t", str(tpl), "-o", str(out)])
    assert rc == 0
    assert (out / "report").read_text() == "contexts: 2"


def test_no_command_prints_help(capsys):
    assert main([]) == 1
    assert "validate" in capsys.readouterr().out
