from .mermaid import MermaidGenerator
from .jinja2_gen import Jinja2Generator

GENERATORS = {
    "mermaid": MermaidGenerator,
    "generic": Jinja2Generator,
}

__all__ = ["MermaidGenerator", "Jinja2Generator", "GENERATORS"]
