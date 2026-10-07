from .mermaid import MermaidGenerator
from .plantuml import PlantUMLGenerator
from .jinja2_gen import Jinja2Generator

GENERATORS = {
    "mermaid": MermaidGenerator,
    "plantuml": PlantUMLGenerator,
    "generic": Jinja2Generator,
}

__all__ = ["MermaidGenerator", "PlantUMLGenerator", "Jinja2Generator", "GENERATORS"]
