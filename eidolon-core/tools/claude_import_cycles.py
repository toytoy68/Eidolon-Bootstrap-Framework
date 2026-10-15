# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_import_cycles.py
# Description : Cartographie statique des cycles d'imports d'un paquet Python (Claude, G236-10)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Static import-cycle map (AST only, nothing is imported or executed).

Usage: python tools/claude_import_cycles.py <package_dir> [--json]
Counts every ``import``/``from ... import`` inside the package, including function-level (lazy) imports, which
is where most cycles hide. Limits: dynamic imports (importlib, __import__), conditional platform branches and
re-exports through ``__init__`` attributes are approximated or missed.
"""
import ast
import collections
import json
import pathlib
import sys


def module_graph(package_dir):
    package_dir = pathlib.Path(package_dir).resolve()
    base = package_dir.parent
    modules = {}
    for path in package_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        name = ".".join(path.relative_to(base).with_suffix("").parts)
        modules[name[:-9] if name.endswith(".__init__") else name] = path
    edges, lazy = collections.defaultdict(set), collections.defaultdict(set)
    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        package = name if path.name == "__init__.py" else name.rsplit(".", 1)[0]
        top_level = {id(n) for n in tree.body}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".")
                    parts = parts[:len(parts) - (node.level - 1)]
                    target = ".".join(parts + ([node.module] if node.module else []))
                else:
                    target = node.module or ""
                candidates = [target] + [f"{target}.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
            else:
                continue
            for target in candidates:
                if target in modules and target != name:
                    edges[name].add(target)
                    if id(node) not in top_level:
                        lazy[name].add(target)
    return modules, edges, lazy


def cycles(edges):
    index, low, stack, on, found, counter = {}, {}, [], set(), [], [0]
    sys.setrecursionlimit(20000)

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in sorted(edges.get(v, ())):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on.discard(w)
                component.append(w)
                if w == v:
                    break
            if len(component) > 1:
                found.append(sorted(component))
    for v in sorted(edges):
        if v not in index:
            visit(v)
    return sorted(found, key=lambda c: (-len(c), c))


def report(package_dir):
    modules, edges, lazy = module_graph(package_dir)
    found = cycles(edges)
    fan_in = collections.Counter(t for targets in edges.values() for t in targets)
    return {"modules": len(modules), "imports": sum(len(v) for v in edges.values()),
            "lazy_imports": sum(len(v) for v in lazy.values()),
            "cycles": [{"size": len(c), "modules": c,
                        "lazy_edges_inside": sorted(f"{a} -> {b}" for a in c for b in lazy.get(a, ()) if b in c)}
                       for c in found],
            "top_fan_in": fan_in.most_common(8)}


if __name__ == "__main__":
    result = report(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(result, indent=1, ensure_ascii=False))
    else:
        print(f"{result['modules']} modules, {result['imports']} internal imports "
              f"({result['lazy_imports']} lazy), {len(result['cycles'])} cycles")
        for c in result["cycles"]:
            print(f"- {c['size']} modules; lazy edges inside: {len(c['lazy_edges_inside'])}")
            print("   " + ", ".join(c["modules"][:12]) + (" ..." if c["size"] > 12 else ""))
