"""BDD/Cucumber-style tag expression filtering for CML doc tags.

Supported syntax (adapted for @key:value tags):

    @stakeholder:employee            has tag with value
    @stakeholder                     has tag key (any value)
    not @deprecated                  negation
    @a and @b                      conjunction
    @a or @b                       disjunction
    ( @a or @b ) and not @c        parentheses

Keywords (and/or/not) are case-insensitive.
"""

import copy
import re
from typing import Any, Dict, List, Optional, Tuple


class TagExpressionError(ValueError):
    pass


_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<lpar>\()
      | (?P<rpar>\))
      | (?P<and>and\b)
      | (?P<or>or\b)
      | (?P<not>not\b)
      | (?P<tag>@[A-Za-z_][A-Za-z0-9_.\-]*(?::[^\s()]+)?)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# AST nodes: ("tag", key, Optional[value]) | ("and", l, r) | ("or", l, r) | ("not", x)
_Node = Tuple


def _tokenize(expression: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    pos = 0
    while pos < len(expression):
        if expression[pos:].strip() == "":
            break
        match = _TOKEN_RE.match(expression, pos)
        if not match:
            raise TagExpressionError(
                f"Invalid token at position {pos} in tag expression: {expression[pos:]!r}"
            )
        pos = match.end()
        for kind, value in match.groupdict().items():
            if value is not None:
                tokens.append((kind, value))
                break
    if not tokens:
        raise TagExpressionError("Empty tag expression")
    return tokens


def parse(expression: str) -> _Node:
    """Parse a tag expression string into an AST."""
    tokens = _tokenize(expression)
    node, index = _parse_or(tokens, 0)
    if index != len(tokens):
        raise TagExpressionError(
            f"Unexpected token {tokens[index][1]!r} in tag expression: {expression!r}"
        )
    return node


def _parse_or(tokens: List[Tuple[str, str]], index: int) -> Tuple[_Node, int]:
    left, index = _parse_and(tokens, index)
    while index < len(tokens) and tokens[index][0] == "or":
        right, index = _parse_and(tokens, index + 1)
        left = ("or", left, right)
    return left, index


def _parse_and(tokens: List[Tuple[str, str]], index: int) -> Tuple[_Node, int]:
    left, index = _parse_unary(tokens, index)
    while index < len(tokens) and tokens[index][0] == "and":
        right, index = _parse_unary(tokens, index + 1)
        left = ("and", left, right)
    return left, index


def _parse_unary(tokens: List[Tuple[str, str]], index: int) -> Tuple[_Node, int]:
    if index >= len(tokens):
        raise TagExpressionError("Unexpected end of tag expression")
    kind, value = tokens[index]
    if kind == "not":
        operand, index = _parse_unary(tokens, index + 1)
        return ("not", operand), index
    if kind == "lpar":
        node, index = _parse_or(tokens, index + 1)
        if index >= len(tokens) or tokens[index][0] != "rpar":
            raise TagExpressionError("Missing closing parenthesis in tag expression")
        return node, index + 1
    if kind == "tag":
        body = value[1:]
        if ":" in body:
            key, tag_value = body.split(":", 1)
            return ("tag", key, tag_value), index + 1
        return ("tag", body, None), index + 1
    raise TagExpressionError(f"Unexpected token {value!r} in tag expression")


def evaluate(expression: Any, tags: Dict[str, List[str]]) -> bool:
    """Evaluate a tag expression (string or parsed AST) against a tags dict."""
    node = parse(expression) if isinstance(expression, str) else expression
    op = node[0]
    if op == "tag":
        key, value = node[1], node[2]
        if key not in tags:
            return False
        return value is None or value in tags[key]
    if op == "and":
        return evaluate(node[1], tags) and evaluate(node[2], tags)
    if op == "or":
        return evaluate(node[1], tags) or evaluate(node[2], tags)
    if op == "not":
        return not evaluate(node[1], tags)
    raise TagExpressionError(f"Unknown expression node: {node!r}")  # pragma: no cover


def _matches(obj: Any, node: _Node) -> bool:
    return hasattr(obj, "_doc_tags") and evaluate(node, obj._doc_tags)


def filter_model(model: Any, expression: str) -> Any:
    """Return a copy of the CML model pruned by a tag expression.

    An object is kept when it matches the expression itself or any of
    its (kept) descendants matches. Objects without doc tags never match.
    """
    from .cml_objects import CML

    node = parse(expression)
    filtered = CML()
    if model.parse_results:
        filtered.parse_results = model.parse_results

    def filter_aggregate(agg):
        new = copy.copy(agg)
        kept_any = False
        for field_name in (
            "entities",
            "value_objects",
            "domain_events",
            "command_events",
            "data_transfer_objects",
            "enums",
            "services",
            "repositories",
            "resources",
            "consumers",
            "basic_types",
        ):
            children = getattr(agg, field_name, [])
            kept = [c for c in children if _matches(c, node)]
            setattr(new, field_name, kept)
            kept_any = kept_any or bool(kept)
        return new if (_matches(agg, node) or kept_any) else None

    def filter_context(ctx):
        new = copy.copy(ctx)
        new.aggregates = [a for a in (filter_aggregate(x) for x in ctx.aggregates) if a]
        new.services = [s for s in ctx.services if _matches(s, node)]
        new.resources = [r for r in ctx.resources if _matches(r, node)]
        new.consumers = [c for c in ctx.consumers if _matches(c, node)]
        new_modules = []
        for module in ctx.modules:
            new_mod = copy.copy(module)
            new_mod.aggregates = [
                a for a in (filter_aggregate(x) for x in module.aggregates) if a
            ]
            new_mod.domain_objects = [
                o for o in module.domain_objects if _matches(o, node)
            ]
            new_mod.services = [s for s in module.services if _matches(s, node)]
            new_mod.resources = [r for r in module.resources if _matches(r, node)]
            new_mod.consumers = [c for c in module.consumers if _matches(c, node)]
            if _matches(module, node) or (
                new_mod.aggregates
                or new_mod.domain_objects
                or new_mod.services
                or new_mod.resources
                or new_mod.consumers
            ):
                new_modules.append(new_mod)
        new.modules = new_modules
        new_app = None
        if ctx.application:
            app = copy.copy(ctx.application)
            app.command_events = [e for e in ctx.application.command_events if _matches(e, node)]
            app.domain_events = [e for e in ctx.application.domain_events if _matches(e, node)]
            app.services = [s for s in ctx.application.services if _matches(s, node)]
            if _matches(ctx.application, node) or (
                app.command_events or app.domain_events or app.services
            ):
                new_app = app
        new.application = new_app
        if _matches(ctx, node) or (
            new.aggregates or new.services or new.resources or new.consumers or new.modules or new_app
        ):
            return new
        return None

    for domain in model.domains:
        new_domain = copy.copy(domain)
        new_domain.subdomains = []
        kept_any = False
        for sd in domain.subdomains:
            new_sd = copy.copy(sd)
            new_sd.entities = [e for e in getattr(sd, "entities", []) if _matches(e, node)]
            new_sd.services = [s for s in getattr(sd, "services", []) if _matches(s, node)]
            if _matches(sd, node) or new_sd.entities or new_sd.services:
                new_domain.subdomains.append(new_sd)
                kept_any = True
        if _matches(domain, node) or kept_any:
            filtered.domains.append(new_domain)

    filtered.context_maps = [cm for cm in model.context_maps if _matches(cm, node)]

    for ctx in model.contexts:
        kept = filter_context(ctx)
        if kept:
            filtered.contexts.append(kept)

    filtered.use_cases = [u for u in model.use_cases if _matches(u, node)]
    filtered.user_stories = [u for u in model.user_stories if _matches(u, node)]
    filtered.value_registers = [v for v in model.value_registers if _matches(v, node)]
    filtered.traits = [t for t in model.traits if _matches(t, node)]

    for app in model.tactic_applications:
        new_app = copy.copy(app)
        new_app.domain_objects = [o for o in app.domain_objects if _matches(o, node)]
        new_app.services = [s for s in app.services if _matches(s, node)]
        new_app.resources = [r for r in app.resources if _matches(r, node)]
        new_app.consumers = [c for c in app.consumers if _matches(c, node)]
        if _matches(app, node) or (
            new_app.domain_objects or new_app.services or new_app.resources or new_app.consumers
        ):
            filtered.tactic_applications.append(new_app)

    return filtered
