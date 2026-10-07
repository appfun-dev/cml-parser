from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from ..cml_objects import CML


class Jinja2Generator:
    """Generates arbitrary text output by rendering a Jinja2 template
    with the parsed CML model (replaces the Freemarker 'generic'
    generator of the Java CLI).

    Template context:
    - model: the CML model object (dataclasses; attribute access works)
    - filename: name of the input CML file (may be None)
    """

    name = "generic"

    def generate(
        self,
        model: CML,
        output_dir: str,
        template: Optional[str] = None,
        output_file: Optional[str] = None,
        **kwargs,
    ) -> List[Path]:
        if not template:
            raise ValueError("Jinja2 generator requires a template (-t/--template)")
        template_path = Path(template)
        if not template_path.is_file():
            raise FileNotFoundError(f"Template not found: {template}")

        env = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            keep_trailing_newline=True,
        )
        env.filters["to_dict"] = lambda obj: asdict(obj) if is_dataclass(obj) else obj
        tmpl = env.get_template(template_path.name)

        rendered = tmpl.render(
            model=model,
            filename=model.parse_results.filename if model.parse_results else None,
        )

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        filename = output_file or template_path.stem
        path = out / filename
        path.write_text(rendered, encoding="utf-8")
        return [path]
