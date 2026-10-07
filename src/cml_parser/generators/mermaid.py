import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..cml_objects import (
    CML,
    Aggregate,
    Attribute,
    Context,
    ContextMap,
    Operation,
    Relationship,
)

_VISIBILITY_SYMBOLS = {"public": "+", "private": "-", "protected": "#"}


def _safe_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _visibility(attr_or_op) -> str:
    return _VISIBILITY_SYMBOLS.get(getattr(attr_or_op, "visibility", None) or "", "+")


def _format_attribute(attr: Attribute) -> str:
    collection = f"~{attr.collection_type}~" if attr.collection_type else ""
    key = " «key»" if attr.is_key else ""
    return f"{_visibility(attr)}{attr.type}{collection} {attr.name}{key}"


def _format_operation(op: Operation) -> str:
    params = ", ".join(
        f"{p.type} {p.name}" for p in op.parameters
    )
    ret = f" {op.return_type}" if op.return_type else ""
    abstract = "*" if op.is_abstract else ""
    return f"{_visibility(op)}{op.name}({params}){ret}{abstract}"


class MermaidGenerator:
    """Generates Mermaid diagrams from a parsed CML model.

    Produces:
    - one class diagram (`.mmd`) per BoundedContext containing its
      aggregates, entities, value objects, domain events, enums, services
      and their relationships
    - one flowchart diagram per ContextMap showing the contexts and
      their relationships
    """

    name = "mermaid"

    def generate(self, model: CML, output_dir: str, **kwargs) -> List[Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        written: List[Path] = []

        contexts = [c for c in model.contexts if not self._is_placeholder(c)]
        for ctx in contexts:
            path = out / f"{_safe_id(ctx.name)}.mmd"
            path.write_text(self._render_context_class_diagram(ctx), encoding="utf-8")
            written.append(path)

        for cm in model.context_maps:
            path = out / f"{_safe_id(cm.name)}_context_map.mmd"
            path.write_text(self._render_context_map(cm), encoding="utf-8")
            written.append(path)

        return written

    @staticmethod
    def _is_placeholder(ctx: Context) -> bool:
        return not (ctx.aggregates or ctx.modules or ctx.services or ctx.application)

    # --- class diagram per bounded context ---

    def _render_context_class_diagram(self, ctx: Context) -> str:
        lines = ["classDiagram"]
        lines.append(f"    %% BoundedContext: {ctx.name}")
        relations: List[str] = []
        defined_types = set()

        def emit_domain_object(obj, stereotype: str, indent: str = "    "):
            defined_types.add(obj.name)
            lines.append(f"{indent}class {obj.name} {{")
            lines.append(f"{indent}    <<{stereotype}>>")
            for attr in getattr(obj, "attributes", []):
                lines.append(f"{indent}    {_format_attribute(attr)}")
            for op in getattr(obj, "operations", []):
                lines.append(f"{indent}    {_format_operation(op)}")
            lines.append(f"{indent}}}")
            if getattr(obj, "extends", None):
                relations.append(f"{obj.extends} <|-- {obj.name} : extends")

        def emit_aggregate(agg: Aggregate):
            lines.append(f"    namespace {agg.name} {{")
            lines.append(f"        class {agg.name} {{")
            lines.append("            <<Aggregate>>")
            lines.append("        }")
            for ent in agg.entities:
                stereotype = "Aggregate Root" if ent.is_aggregate_root else "Entity"
                emit_domain_object(ent, stereotype, indent="        ")
            for vo in agg.value_objects:
                emit_domain_object(vo, "Value Object", indent="        ")
            for de in agg.domain_events:
                emit_domain_object(de, "Domain Event", indent="        ")
            for ce in agg.command_events:
                emit_domain_object(ce, "Command Event", indent="        ")
            for dto in agg.data_transfer_objects:
                emit_domain_object(dto, "DTO", indent="        ")
            for enum in agg.enums:
                lines.append(f"        class {enum.name} {{")
                lines.append("            <<Enumeration>>")
                for value in enum.values:
                    lines.append(f"            {value}")
                lines.append("        }")
            for svc in agg.services:
                emit_domain_object(svc, "Service", indent="        ")
            for repo in agg.repositories:
                emit_domain_object(repo, "Repository", indent="        ")
            lines.append("    }")
            # aggregate containment relations
            for ent in agg.entities:
                relations.append(f"{agg.name} *-- {ent.name}")
            for vo in agg.value_objects:
                relations.append(f"{agg.name} *-- {vo.name}")

        for agg in ctx.aggregates:
            emit_aggregate(agg)
        for module in ctx.modules:
            lines.append(f"    namespace {module.name} {{")
            for obj in module.domain_objects:
                emit_domain_object(obj, type(obj).__name__, indent="        ")
            lines.append("    }")
        for svc in ctx.services:
            emit_domain_object(svc, "Service")
        if ctx.application:
            for obj in ctx.application.domain_events:
                emit_domain_object(obj, "Domain Event")
            for obj in ctx.application.command_events:
                emit_domain_object(obj, "Command Event")
            for svc in ctx.application.services:
                emit_domain_object(svc, "Service")

        # reference relations between known types
        for agg in ctx.aggregates:
            for obj in [*agg.entities, *agg.value_objects, *agg.domain_events]:
                for attr in getattr(obj, "attributes", []):
                    if attr.is_reference or attr.type in defined_types:
                        if attr.type in defined_types and attr.type != obj.name:
                            relations.append(f"{obj.name} --> {attr.type}")

        seen = set()
        for rel in relations:
            if rel not in seen:
                seen.add(rel)
                lines.append(f"    {rel}")
        return "\n".join(lines) + "\n"

    # --- context map diagram ---

    def _render_context_map(self, cm: ContextMap) -> str:
        lines = ["flowchart LR"]
        lines.append(f"    %% ContextMap: {cm.name}")

        context_names = []
        for ctx in cm.contexts:
            if ctx.name not in context_names:
                context_names.append(ctx.name)
        for rel in cm.relationships:
            for endpoint in (rel.left, rel.right):
                if endpoint.name not in context_names:
                    context_names.append(endpoint.name)

        for name in context_names:
            lines.append(f"    {_safe_id(name)}[{name}]")

        for rel in cm.relationships:
            lines.append(f"    {self._render_relationship(rel)}")
        return "\n".join(lines) + "\n"

    def _render_relationship(self, rel: Relationship) -> str:
        label_parts = [rel.type] if rel.type and rel.type != "Unknown" else []
        if rel.upstream_roles:
            label_parts.append("U: " + ",".join(rel.upstream_roles))
        if rel.downstream_roles:
            label_parts.append("D: " + ",".join(rel.downstream_roles))
        label = "<br/>".join(label_parts)

        if rel.type == "Partnership":
            source, target, arrow = rel.left, rel.right, "<-->"
        elif rel.type == "Shared-Kernel":
            source, target, arrow = rel.left, rel.right, "---"
        elif rel.upstream is not None and rel.downstream is not None:
            source, target, arrow = rel.upstream, rel.downstream, "-->"
        else:
            source, target, arrow = rel.left, rel.right, "-->"

        left = _safe_id(source.name)
        right = _safe_id(target.name)
        if label:
            return f"{left} {arrow}|\"{label}\"| {right}"
        return f"{left} {arrow} {right}"
