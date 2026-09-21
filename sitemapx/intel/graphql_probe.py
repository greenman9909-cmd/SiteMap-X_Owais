from __future__ import annotations

from typing import Any
import re

INTROSPECTION_QUERY = r'''query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind name description
      fields(includeDeprecated: true) {
        name description isDeprecated deprecationReason
        args { name description defaultValue type { ...TypeRef } }
        type { ...TypeRef }
      }
      inputFields { name description defaultValue type { ...TypeRef } }
      interfaces { kind name }
      enumValues(includeDeprecated: true) { name description isDeprecated deprecationReason }
      possibleTypes { kind name }
    }
    directives {
      name description locations
      args { name description defaultValue type { ...TypeRef } }
    }
  }
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
}'''


def extract_operation_names(text: str) -> list[tuple[str, str]]:
    found = []
    for m in re.finditer(r"\b(query|mutation|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)", text):
        found.append((m.group(1), m.group(2)))
    return list(dict.fromkeys(found))


def _type_name(node: dict[str, Any]) -> str:
    kind = node.get("kind")
    if kind == "NON_NULL":
        return _type_name(node.get("ofType") or {}) + "!"
    if kind == "LIST":
        return "[" + _type_name(node.get("ofType") or {}) + "]"
    if node.get("name"):
        return str(node["name"])
    if node.get("ofType"):
        return _type_name(node["ofType"])
    return "Unknown"


def _args(args: list[dict[str, Any]] | None) -> str:
    parts = []
    for arg in args or []:
        item = f"{arg.get('name')}: {_type_name(arg.get('type') or {})}"
        if arg.get("defaultValue") is not None:
            item += f" = {arg.get('defaultValue')}"
        parts.append(item)
    return "(" + ", ".join(parts) + ")" if parts else ""


def schema_to_sdl(data: dict[str, Any]) -> str:
    schema = data.get("data", {}).get("__schema", {}) if isinstance(data, dict) else {}
    lines: list[str] = []
    roots = []
    for key, label in (("queryType", "query"), ("mutationType", "mutation"), ("subscriptionType", "subscription")):
        name = (schema.get(key) or {}).get("name")
        if name:
            roots.append(f"  {label}: {name}")
    if roots:
        lines += ["schema {", *roots, "}", ""]

    for t in schema.get("types", []) or []:
        name = t.get("name")
        kind = t.get("kind")
        if not name or str(name).startswith("__"):
            continue
        if kind == "SCALAR":
            lines += [f"scalar {name}", ""]
        elif kind in {"OBJECT", "INTERFACE"}:
            prefix = "type" if kind == "OBJECT" else "interface"
            impl = ""
            if kind == "OBJECT":
                interfaces = [i.get("name") for i in (t.get("interfaces") or []) if i.get("name")]
                if interfaces:
                    impl = " implements " + " & ".join(interfaces)
            lines.append(f"{prefix} {name}{impl} {{")
            for f in t.get("fields") or []:
                lines.append(f"  {f.get('name')}{_args(f.get('args'))}: {_type_name(f.get('type') or {})}")
            lines += ["}", ""]
        elif kind == "INPUT_OBJECT":
            lines.append(f"input {name} {{")
            for f in t.get("inputFields") or []:
                item = f"  {f.get('name')}: {_type_name(f.get('type') or {})}"
                if f.get("defaultValue") is not None:
                    item += f" = {f.get('defaultValue')}"
                lines.append(item)
            lines += ["}", ""]
        elif kind == "ENUM":
            lines.append(f"enum {name} {{")
            for e in t.get("enumValues") or []:
                lines.append(f"  {e.get('name')}")
            lines += ["}", ""]
        elif kind == "UNION":
            members = [x.get("name") for x in (t.get("possibleTypes") or []) if x.get("name")]
            lines += [f"union {name} = " + " | ".join(members), ""]
    return "\n".join(lines).rstrip() + "\n"
