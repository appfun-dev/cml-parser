from .mermaid import MermaidGenerator
from .plantuml import PlantUMLGenerator
from .jinja2_gen import Jinja2Generator
from .yaml_gen import YamlGenerator

GENERATORS = {
    "mermaid": MermaidGenerator,
    "plantuml": PlantUMLGenerator,
    "generic": Jinja2Generator,
    "yaml": YamlGenerator,
}

__all__ = ["MermaidGenerator", "PlantUMLGenerator", "Jinja2Generator", "YamlGenerator", "GENERATORS"]
