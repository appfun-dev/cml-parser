import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from cml_parser.generators import GENERATORS
from cml_parser.parser import parse_file_safe


SAMPLE = """
ContextMap ShopMap {
    contains Sales, Shipping
    Sales [D] <- [U] Shipping
}

BoundedContext Sales {
    Aggregate Orders {
        Entity Order {
            aggregateRoot
            String status
        }
    }
}

BoundedContext Shipping

UserStory Customers {
    As a "Shop employee"
        I want to create a "CustomerProfile"
    so that "I can manage customer data."
}

UseCase PlaceOrder {
    actor "Customer"
    interactions create an "Order"
    benefit "goods purchased"
}
"""


def _parse(tmp_path):
    path = tmp_path / "sample.cml"
    path.write_text(SAMPLE)
    model = parse_file_safe(str(path))
    assert model.parse_results.ok
    return model


def test_yaml_generator_registered():
    assert "yaml" in GENERATORS


def test_yaml_generator_full_model(tmp_path):
    model = _parse(tmp_path)
    out_dir = tmp_path / "out"
    written = GENERATORS["yaml"]().generate(model, str(out_dir))
    assert len(written) == 1
    data = yaml.safe_load(written[0].read_text())

    assert list(data.keys()) == [
        "domains", "context_maps", "contexts", "use_cases", "user_stories",
        "stakeholder_sections", "stakeholder_groups", "stakeholders",
        "value_registers", "traits", "tactic_applications", "service_cutter",
    ]
    assert "parse_results" not in data

    story = data["user_stories"][0]
    assert story["name"] == "Customers"
    assert story["role"] == "Shop employee"
    assert story["benefit"] == "I can manage customer data."

    use_case = data["use_cases"][0]
    assert use_case["name"] == "PlaceOrder"
    assert use_case["actor"] == "Customer"


def test_yaml_generator_emits_ref_markers_for_shared_objects(tmp_path):
    model = _parse(tmp_path)
    written = GENERATORS["yaml"]().generate(model, str(tmp_path / "out"))
    text = written[0].read_text()

    data = yaml.safe_load(text)
    cm = data["context_maps"][0]
    contexts_in_map = cm.get("contexts") or []
    assert any(
        isinstance(c, dict) and "$ref" in (c.get("context_map") or {})
        for c in contexts_in_map
    )
    assert "$ref:" in text


def test_yaml_generator_output_file_option(tmp_path):
    model = _parse(tmp_path)
    written = GENERATORS["yaml"]().generate(model, str(tmp_path / "out"), output_file="model_dump.yml")
    assert written[0].name == "model_dump.yml"
    assert yaml.safe_load(written[0].read_text())["contexts"]
