import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .parser import parse_file_safe
from .generators import GENERATORS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cml",
        description="CML Parser CLI - validate CML files and generate diagrams/text.",
    )
    sub = parser.add_subparsers(dest="command")

    validate = sub.add_parser("validate", help="Validate a CML file.")
    validate.add_argument("-i", "--input", required=True, help="Path to the CML file to validate.")

    generate = sub.add_parser("generate", help="Generate output from a CML file.")
    generate.add_argument("-i", "--input", required=True, help="Path to the CML input file.")
    generate.add_argument(
        "-g",
        "--generator",
        required=True,
        choices=sorted(GENERATORS.keys()),
        help="Generator to use: 'mermaid' (Mermaid class/context-map diagrams), "
        "'plantuml' (PlantUML class/component diagrams), "
        "'generic' (arbitrary text via Jinja2 template).",
    )
    generate.add_argument("-o", "--outputDir", required=True, help="Output directory.")
    generate.add_argument(
        "-t",
        "--template",
        help="Path to the Jinja2 template (only used by the 'generic' generator).",
    )
    generate.add_argument(
        "-f",
        "--outputFile",
        help="Name of the generated file (only used by the 'generic' generator).",
    )
    generate.add_argument(
        "--tags",
        help="BDD/Cucumber-style tag expression to filter the model before "
        "generation, e.g. '@stakeholder:employee and not @deprecated'. "
        "Objects are kept when they or any descendant matches.",
    )
    return parser


def _cmd_validate(input_path: str) -> int:
    if not Path(input_path).is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1
    cml = parse_file_safe(input_path)
    if cml.parse_results.ok:
        print(f"'{input_path}' is valid.")
        return 0
    print(f"Validation failed for '{input_path}':", file=sys.stderr)
    for err in cml.parse_results.errors:
        print(f"  {err.pretty()}", file=sys.stderr)
    return 1


def _cmd_generate(args: argparse.Namespace) -> int:
    if not Path(args.input).is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1
    cml = parse_file_safe(args.input)
    if not cml.parse_results.ok:
        print(f"Cannot generate from invalid CML file '{args.input}':", file=sys.stderr)
        for err in cml.parse_results.errors:
            print(f"  {err.pretty()}", file=sys.stderr)
        return 1

    model = cml
    if args.tags:
        from .tag_filter import TagExpressionError, filter_model
        try:
            model = filter_model(cml, args.tags)
        except TagExpressionError as e:
            print(f"Invalid --tags expression: {e}", file=sys.stderr)
            return 1

    generator = GENERATORS[args.generator]()
    try:
        written = generator.generate(
            model,
            args.outputDir,
            template=args.template,
            output_file=args.outputFile,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        return 1

    for path in written:
        print(f"Generated: {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(args.input)
    if args.command == "generate":
        return _cmd_generate(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
