# CML Parser

[![CI](https://github.com/martin882003/cml-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/martin882003/cml-parser/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cml-parser.svg)](https://pypi.org/project/cml-parser/)
[![codecov](https://codecov.io/github/martin882003/cml-parser/graph/badge.svg?token=LBFYNPZQE0)](https://codecov.io/github/martin882003/cml-parser)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Python library to parse the Context Mapper Language (CML) using ANTLR4. It aims to cover the language defined by the Context Mapper project and is validated against the official sample models.

**Docs:** https://martin882003.github.io/cml-parser

## Context

CML is the DSL for Context Mapper, a toolkit for strategic/tactical Domain-Driven Design modeling. Reference material and canonical examples are maintained by the Context Mapper team:
- Language docs: https://contextmapper.org/
- Official examples repository: https://github.com/ContextMapper/context-mapper-examples

## Installation

### Using uv (Recommended) ⚡

[uv](https://docs.astral.sh/uv/) is a fast Python package manager that's 10-100x faster than pip:

```bash
# Install from PyPI
uv pip install cml-parser

# Or clone and install from source
git clone https://github.com/martin882003/cml-parser.git
cd cml-parser
uv sync
```

### Using pip

```bash
pip install cml-parser
```

### From Source (pip)

```bash
git clone https://github.com/martin882003/cml-parser.git
cd cml-parser
pip install -e .
```

## Usage

```python
from cml_parser import parse_file

# Strict mode: raises CmlSyntaxError on parse errors
model = parse_file("path/to/model.cml")

# Safe mode: returns CML object with parse_results
from cml_parser import parse_file_safe
cml = parse_file_safe("path/to/model.cml")

if cml.parse_results.ok:
    print(f"✓ Parsed successfully")
    print(f"  Domains: {len(cml.domains)}")
    print(f"  Context Maps: {len(cml.context_maps)}")
    
    # Access tactical DDD elements
    for cm in cml.context_maps:
        for ctx in cm.contexts:
            for agg in ctx.aggregates:
                print(f"  Aggregate: {agg.name}")
                for entity in agg.entities:
                    print(f"    Entity: {entity.name}")
                    for attr in entity.attributes:
                        print(f"      - {attr.name}: {attr.type}")
else:
    print("Parse errors:")
    for err in cml.parse_results.errors:
        print(f"  {err.pretty()}")
```

## Command Line Interface

Installing the package provides the `cml` command:

```bash
# Validate a CML file (exit 1 on syntax errors)
cml validate -i model.cml

# Generate Mermaid diagrams (class diagram per BoundedContext,
# flowchart per ContextMap)
cml generate -i model.cml -g mermaid -o ./out

# Generate PlantUML diagrams
cml generate -i model.cml -g plantuml -o ./out

# Render arbitrary text with a Jinja2 template
cml generate -i model.cml -g generic -t examples/templates/glossary.md.j2 -o ./out -f glossary.md

# Filter the model with a BDD/Cucumber-style tag expression before generating
cml generate -i model.cml -g mermaid -o ./out --tags '@domain:claims and not @deprecated:true'
```

Doc comments (`//`, `/* */`) above or inside blocks are attached to the parsed
objects (`leading_comment`, `inner_comment`), and `@key:value` tags within them
are extracted into `_doc_tags` for filtering and templating.

See [docs/cli.md](docs/cli.md) for the full CLI reference, template context
variables, and tag expression syntax.

## Architecture

This parser is built with **ANTLR4**, providing:
- ✅ Robust parsing of CML syntax
- ✅ Full support for tactical DDD elements (Entities, ValueObjects, Aggregates, etc.)
- ✅ Strategic DDD (BoundedContexts, ContextMaps, Relationships)
- ✅ Deferred reference linking for forward declarations
- ✅ Rich Python object model with accessor methods

## Development

### Setup with uv

```bash
git clone https://github.com/martin882003/cml-parser.git
cd cml-parser
uv sync
uv run pytest
```

### Setup with pip

```bash
git clone https://github.com/martin882003/cml-parser.git
cd cml-parser
python -m venv venv
source venv/bin/activate
pip install -e .
pytest
```

### Regenerating the Parser

If you modify the ANTLR4 grammar (`src/cml_parser/CML.g4`):

```bash
# Install development dependencies
uv add --dev antlr4-tools

# Regenerate parser
uv run antlr4 -Dlanguage=Python3 -visitor -o src/cml_parser/antlr src/cml_parser/CML.g4
```

## License

MIT License — see [LICENSE](LICENSE).

## Contact

- Maintainer: Martin Herran — martin882003@gmail.com

## Contributing

Contributions are welcome! Please:
1. Open an issue describing the change (grammar gaps, bugs, docs).
2. Keep coverage: ensure `pytest` passes and new constructs are represented in `examples/` or new fixtures.
3. Submit a PR with a concise summary of the change.
