from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

import yaml

from ..cml_objects import CML

_SKIP_FIELDS = {"parse_results"}


def _ref_marker(obj: Any) -> str:
    name = getattr(obj, "name", None)
    label = type(obj).__name__
    return f"{label}:{name}" if name else label


def _to_plain(obj: Any, seen: set) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _to_plain(v, seen) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(item, seen) for item in obj]
    if is_dataclass(obj):
        oid = id(obj)
        if oid in seen:
            return {"$ref": _ref_marker(obj)}
        seen.add(oid)
        result = {}
        for f in fields(obj):
            if f.name in _SKIP_FIELDS:
                continue
            result[f.name] = _to_plain(getattr(obj, f.name), seen)
        return result
    return str(obj)


class YamlGenerator:
    """Dumps the full parsed CML model to a single YAML document.

    Circular/duplicate object references (e.g. resolved `*_refs` links
    pointing at objects already serialized elsewhere in the tree) are
    emitted as `{"$ref": "<Class>:<name>"}` markers so the output stays
    finite and free of runaway recursion.
    """

    name = "yaml"

    def generate(self, model: CML, output_dir: str, output_file: Optional[str] = None, **kwargs) -> List[Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        if output_file:
            filename = output_file
        else:
            source = model.parse_results.filename if model.parse_results else None
            stem = Path(source).stem if source else "model"
            filename = f"{stem}.yaml"

        data = _to_plain(model, set())
        path = out / filename
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120),
            encoding="utf-8",
        )
        return [path]
