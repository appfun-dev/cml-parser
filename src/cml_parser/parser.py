from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Any, Union, Set
import argparse
import json
import sys
import os

from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener

from .antlr.CMLLexer import CMLLexer
from .antlr.CMLParser import CMLParser
from .cml_model_builder import CMLModelBuilder
from .cml_objects import (
    CML,
    ParseResult,
    Diagnostic,
    Domain,
    Subdomain,
    SubdomainType,
    ContextMap,
    Context,
    Relationship,
    RelationshipType,
    UseCase,
    Entity,
    ValueObject,
    DomainEvent,
    Enum,
    Aggregate,
    Service,
    Repository,
    Attribute,
    Operation,
    Parameter
)

class CmlSyntaxError(Exception):
    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.pretty())
        self.diagnostic = diagnostic

class CMLErrorListener(ErrorListener):
    def __init__(self, filename: str = None):
        super().__init__()
        self.filename = filename
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(Diagnostic(
            message=msg,
            line=line,
            col=column,
            filename=self.filename
        ))

def parse_file(file_path) -> CML:
    """
    Strict parsing of a .cml file. Raises CmlSyntaxError on failure.
    Supports import statements - imported files are resolved relative to the main file.
    """
    return _parse_with_imports(path=file_path, text=None, strict=True)

def parse_file_safe(file_path) -> CML:
    """
    Non-strict parsing of a .cml file. Returns CML with parse_results containing errors.
    Supports import statements - imported files are resolved relative to the main file.
    """
    return _parse_with_imports(path=file_path, text=None, strict=False)

def parse_text(text: str, *, filename: Optional[str] = None, strict: bool = True) -> CML:
    """
    Parse CML from a text string.
    Note: Import statements in text will be resolved relative to filename if provided.
    """
    return _parse_with_imports(path=filename, text=text, strict=strict)


def _parse_with_imports(
    path: Optional[str],
    text: Optional[str],
    strict: bool,
    _parsed_files: Optional[Set[str]] = None
) -> CML:
    """
    Parse a CML file with support for import statements.

    Import resolution:
    - Imports are resolved relative to the directory of the importing file
    - Circular imports are detected and prevented
    - Imported models are merged into the main model

    Args:
        path: Path to the CML file (used for import resolution)
        text: Optional text content (if provided, path is only used for import resolution)
        strict: If True, raises CmlSyntaxError on parse errors
        _parsed_files: Internal set to track already-parsed files (prevents circular imports)
    """
    # Track parsed files to prevent circular imports
    if _parsed_files is None:
        _parsed_files = set()

    # Resolve absolute path for deduplication
    abs_path = None
    if path:
        abs_path = str(Path(path).resolve())
        if abs_path in _parsed_files:
            # Already parsed this file - return empty CML to prevent duplication
            return CML()
        _parsed_files.add(abs_path)

    # Parse the single file (without recursing into imports yet)
    cml, builder_imports, errors = _parse_single_file(path, text, strict)

    # Resolve and parse imports
    if builder_imports and path:
        base_dir = Path(path).parent
        for import_path in builder_imports:
            resolved_path = _resolve_import_path(import_path, base_dir)
            if resolved_path:
                try:
                    imported_cml = _parse_with_imports(
                        path=str(resolved_path),
                        text=None,
                        strict=strict,
                        _parsed_files=_parsed_files
                    )
                    _merge_cml(cml, imported_cml)
                except CmlSyntaxError as e:
                    errors.append(Diagnostic(
                        message=f"Error in imported file '{import_path}': {e.diagnostic.message}",
                        filename=str(path)
                    ))
                    if strict:
                        raise
                except FileNotFoundError:
                    errors.append(Diagnostic(
                        message=f"Import not found: '{import_path}'",
                        filename=str(path)
                    ))
                    if strict:
                        raise CmlSyntaxError(errors[-1])
                except Exception as e:
                    errors.append(Diagnostic(
                        message=f"Error processing import '{import_path}': {str(e)}",
                        filename=str(path)
                    ))
                    if strict:
                        raise CmlSyntaxError(errors[-1])

    # Update parse results with any import errors
    if cml.parse_results:
        cml.parse_results.errors.extend(errors)

    return cml


def _parse_single_file(
    path: Optional[str],
    text: Optional[str],
    strict: bool
) -> tuple:
    """
    Parse a single CML file without following imports.

    Returns:
        Tuple of (cml_model, imports_list, errors_list)
    """
    filename = str(path) if path else None
    source = text
    if path and source is None:
        source = Path(path).read_text(encoding="utf-8")

    input_stream = InputStream(source)
    lexer = CMLLexer(input_stream)

    # Custom error listener
    error_listener = CMLErrorListener(filename)
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)

    token_stream = CommonTokenStream(lexer)
    parser = CMLParser(token_stream)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    # Parse
    tree = parser.definitions()

    errors = error_listener.errors
    if errors and strict:
        raise CmlSyntaxError(errors[0])

    # Build model if no critical errors (or even if there are, try best effort)
    cml = CML()
    builder_imports = []

    if not errors or not strict:
        try:
            builder = CMLModelBuilder(filename, token_stream=token_stream)
            cml = builder.visit(tree)
            builder_imports = builder.imports  # Get collected imports
        except Exception as e:
            errors.append(Diagnostic(
                message=f"Model building error: {str(e)}",
                filename=filename
            ))
            if strict:
                raise CmlSyntaxError(errors[-1]) from e

    model = cml if not errors else None

    parse_result = ParseResult(
        model=model,
        errors=errors,
        warnings=[],
        source=source,
        filename=filename
    )

    cml.parse_results = parse_result

    return cml, builder_imports, errors


def _resolve_import_path(import_path: str, base_dir: Path) -> Optional[Path]:
    """
    Resolve an import path relative to a base directory.

    Args:
        import_path: The path specified in the import statement
        base_dir: Directory of the importing file

    Returns:
        Resolved Path object, or None if the file doesn't exist
    """
    # Try relative to base_dir first
    resolved = base_dir / import_path
    if resolved.exists():
        return resolved.resolve()

    # Try as absolute path
    abs_path = Path(import_path)
    if abs_path.is_absolute() and abs_path.exists():
        return abs_path.resolve()

    return None


def _is_placeholder_context(ctx: Context) -> bool:
    """
    Check if a context is a placeholder (created from ContextMap reference).

    A placeholder context typically has:
    - No aggregates
    - No vision statement
    - No implementation technology
    """
    has_aggregates = ctx.aggregates and len(ctx.aggregates) > 0
    has_vision = ctx.vision and len(ctx.vision.strip()) > 0
    has_tech = ctx.implementation_technology and len(ctx.implementation_technology.strip()) > 0

    return not (has_aggregates or has_vision or has_tech)


def _merge_cml(target: CML, source: CML) -> None:
    """
    Merge source CML model into target CML model.

    This merges all top-level elements (contexts, domains, context_maps, etc.)
    from source into target, handling duplicates intelligently:
    - If target has a placeholder (e.g., from ContextMap), replace with full definition
    - Otherwise, skip duplicates
    """
    if source is None:
        return

    # Merge domains
    existing_domain_names = {d.name for d in target.domains}
    for domain in source.domains:
        if domain.name not in existing_domain_names:
            target.domains.append(domain)
            existing_domain_names.add(domain.name)

    # Merge context_maps
    existing_map_names = {cm.name for cm in target.context_maps}
    for cm in source.context_maps:
        if cm.name not in existing_map_names:
            target.context_maps.append(cm)
            existing_map_names.add(cm.name)

    # Merge contexts (bounded contexts)
    # Special handling: replace placeholder contexts with full definitions
    existing_contexts_by_name = {c.name: c for c in target.contexts}
    for ctx in source.contexts:
        existing = existing_contexts_by_name.get(ctx.name)
        if existing is None:
            # New context - add it
            target.contexts.append(ctx)
            existing_contexts_by_name[ctx.name] = ctx
        elif _is_placeholder_context(existing) and not _is_placeholder_context(ctx):
            # Replace placeholder with full definition
            idx = target.contexts.index(existing)
            target.contexts[idx] = ctx
            existing_contexts_by_name[ctx.name] = ctx

    # Merge use_cases
    existing_uc_names = {uc.name for uc in target.use_cases}
    for uc in source.use_cases:
        if uc.name not in existing_uc_names:
            target.use_cases.append(uc)
            existing_uc_names.add(uc.name)

    # Merge user_stories
    existing_story_names = {us.name for us in target.user_stories}
    for us in source.user_stories:
        if us.name not in existing_story_names:
            target.user_stories.append(us)
            existing_story_names.add(us.name)

    # Merge stakeholder_sections
    for ss in source.stakeholder_sections:
        target.stakeholder_sections.append(ss)

    # Merge traits
    existing_trait_names = {t.name for t in target.traits}
    for trait in source.traits:
        if trait.name not in existing_trait_names:
            target.traits.append(trait)
            existing_trait_names.add(trait.name)

    # Merge tactic_applications
    for ta in source.tactic_applications:
        target.tactic_applications.append(ta)

    # Merge value_registers
    for vr in source.value_registers:
        target.value_registers.append(vr)

    # Merge stakeholders
    existing_stakeholder_names = {s.name for s in target.stakeholders}
    for s in source.stakeholders:
        if s.name not in existing_stakeholder_names:
            target.stakeholders.append(s)
            existing_stakeholder_names.add(s.name)

    # Merge stakeholder_groups
    existing_sg_names = {sg.name for sg in target.stakeholder_groups}
    for sg in source.stakeholder_groups:
        if sg.name not in existing_sg_names:
            target.stakeholder_groups.append(sg)
            existing_sg_names.add(sg.name)


# Legacy function for backward compatibility
def _parse_internal(path: Optional[str], text: Optional[str], strict: bool) -> CML:
    """Legacy internal parse function - now delegates to _parse_with_imports."""
    return _parse_with_imports(path, text, strict)


def main(argv=None) -> int:
    """
    Minimal CLI entrypoint to parse a single .cml file.
    """
    args = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="cml-parse", add_help=True)
    parser.add_argument("file", nargs="?", help="Path to .cml file")
    parser.add_argument("--json", action="store_true", help="Emit parse result as JSON")
    parser.add_argument("--summary", action="store_true", help="Print a short success summary")
    parsed = parser.parse_args(args)

    if not parsed.file:
        parser.print_usage(file=sys.stderr)
        return 1

    cml = parse_file_safe(parsed.file)
    if not cml.parse_results.ok:
        print(f"Error parsing {parsed.file}:", file=sys.stderr)
        for err in cml.parse_results.errors:
            print(err.pretty(), file=sys.stderr)
        return 1

    if parsed.json:
        print(json.dumps(cml.parse_results.to_dict(), default=str, indent=2))
        return 0

    if parsed.summary:
        print(f"Successfully parsed {parsed.file}")
        print(f"Domains: {len(cml.domains)}")
        print(f"Contexts: {len(cml.contexts)}")
        print(f"Context Maps: {len(cml.context_maps)}")
        return 0

    print(f"Successfully parsed {parsed.file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
