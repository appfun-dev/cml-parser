# Command Line Interface

The `cml` command validates CML files and generates diagrams or arbitrary
text output (via Jinja2 templates) from them. It is inspired by the
[Context Mapper CLI](https://github.com/ContextMapper/context-mapper-cli),
with Mermaid/PlantUML diagram output and Jinja2 replacing Freemarker.

## Installation

### From PyPI

```bash
pip install cml-parser
# or
uv pip install cml-parser
```

This installs the `cml` console script.

### From source (development)

```bash
git clone https://github.com/martin882003/cml-parser.git
cd cml-parser
uv pip install -e . --python .venv/bin/python
```

Editable install: changes to the source tree take effect immediately.

Without installing, you can run the CLI as a module:

```bash
PYTHONPATH=src python -m cml_parser.cli --help
```

## Commands

```text
cml validate -i <file.cml>
cml generate -i <file.cml> -g <mermaid|plantuml|generic|yaml> -o <dir> [-t template.j2] [-f name] [--tags expr]
```

### validate

Parses a CML file (including `import` resolution) and reports syntax errors.
Exits with code `0` when the file is valid, `1` otherwise.

```bash
cml validate -i model.cml
# 'model.cml' is valid.
```

### generate -g mermaid

Generates [Mermaid](https://mermaid.js.org/) diagrams:

- one **class diagram** (`<Context>.mmd`) per Bounded Context — aggregates as
  namespaces, entities/value objects/enums/services with attributes,
  operations, `extends` and reference relations
- one **flowchart** (`<Map>_context_map.mmd`) per Context Map — contexts as
  nodes, relationships drawn upstream → downstream with type and role labels

```bash
cml generate -i model.cml -g mermaid -o ./out
```

### generate -g plantuml

Generates [PlantUML](https://plantuml.com/) diagrams with the same structure:

- `<Context>.puml` class diagrams (packages per aggregate, stereotypes such
  as `<<Aggregate Root>>`, `<<Entity>>`, `<<Service>>`)
- `<Map>_context_map.puml` component diagrams

```bash
cml generate -i model.cml -g plantuml -o ./out
```

### generate -g yaml

Dumps the full parsed model to a single YAML document
(`<input-stem>.yaml`, overridable with `-f`). Objects referenced more than
once (resolved `*_refs` links, back-references) are emitted as
`$ref: <Class>:<name>` markers to keep the output finite.

```bash
cml generate -i model.cml -g yaml -o ./out
```

### generate -g generic (Jinja2)

Renders an arbitrary text file with a [Jinja2](https://jinja.palletsprojects.com/)
template. The template context provides:

| Variable | Description |
|---|---|
| `model` | The parsed `CML` model (all attributes/methods accessible) |
| `filename` | Path of the input CML file |

| Filter | Description |
|---|---|
| `to_dict` | Convert a dataclass (e.g. a context) to a plain dict |

```bash
cml generate -i model.cml -g generic -t examples/templates/glossary.md.j2 -o ./out -f glossary.md
```

`-f/--outputFile` is optional; without it the output file is named after the
template (`glossary.md.j2` → `glossary.md`).

Ready-made templates live in `examples/templates/`:

- `glossary.md.j2` — domain glossary (domains, contexts with comments and
  tags, aggregates, context maps)
- `tagged_objects.md.j2` — report of all objects carrying a given doc tag
- `user_stories.md.j2` — user stories with role, features, benefit and tags

## Doc comments and tags

Line (`//`) and block (`/* */`) comments are attached to the parsed objects:

- `leading_comment` — the contiguous comment block directly above a block
  (a blank line breaks the attachment)
- `inner_comment` — the first contiguous comment paragraph inside the braces
- `_doc_tags` — `@key:value` tags extracted from both comments

Objects expose `get_tag(key)`, `get_tags(key)`, `has_tag(key, value)`,
`has_tags({k: v})` and `matches_tags(expression)`.

```cml
// @domain:claims @team:ClaimsTeam @criticality:high
BoundedContext ClaimsManagement {
    // @pii:true
    Aggregate Claims {
        Entity Claim { ... }
    }
}
```

## Tag filtering (`--tags`)

`generate` accepts a BDD/Cucumber-style tag expression to filter the model
before generation. An object matching the expression is kept with its whole
subtree; a non-matching object is kept only as an ancestor of a match, with
non-matching siblings pruned.

```text
@stakeholder:employee            tag with value
@stakeholder                     tag key, any value
not @deprecated:true             negation
@a and @b                        conjunction (binds tighter than or)
@a or @b                         disjunction
( @a or @b ) and not @c          parentheses
```

Keywords are case-insensitive. Note that comments must use the `@key:value`
form to be extracted as tags.

Examples (using the tagged `examples/LakesideMutual/LakesideMutual.cml`):

```bash
# only the claims domain
cml generate -i LakesideMutual.cml -g mermaid -o out --tags '@domain:claims'

# high-criticality contexts and aggregates
cml generate -i LakesideMutual.cml -g plantuml -o out --tags '@criticality:high'

# customer domain without the self-service channel
cml generate -i LakesideMutual.cml -g generic -t examples/templates/glossary.md.j2 \
  -o out -f customer-glossary.md --tags '@domain:customer and not @channel:self-service'
```

The same expressions work from Python: `cml.find_by_tags(expr)`,
`cml.filter_by_tags(expr)`, `obj.matches_tags(expr)`.
