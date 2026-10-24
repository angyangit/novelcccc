"""P0 static architecture checks; inspect source without importing it.

This harness implements a deliberately finite import policy. It does not attest
runtime capabilities, database permissions, or arbitrary Python reflection.
"""

import ast
import hashlib
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

import yaml

P0_GATES = frozenset(
    {
        "STATIC",
        "UNIT",
        "SCHEMA_CONTRACT",
        "ARCH_FITNESS",
        "SECRET_DEPENDENCY",
        "POSTGRES_ENV",
    }
)
PROVIDERS = (
    "openai",
    "anthropic",
    "cohere",
    "google.genai",
    "google.generativeai",
    "boto3",
    "botocore",
    "azure.ai",
)
DATABASES = (
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "sqlite3",
    "pymongo",
    "peewee",
    "tortoise",
    "django.db",
)
WEB = ("fastapi", "starlette", "flask", "django", "aiohttp")
WORKFLOWS = ("temporalio", "prefect", "dagster", "celery")
HISTORICAL_ROOTS = frozenset({"plan", "archive", "tests", "scripts"})
PUBLIC_COMMIT = "anovel.canon.commit_service"
REPOSITORY = "anovel.canon.repository"


def _within(name, prefix):
    return name == prefix or name.startswith(prefix + ".")


def _phase_number(value):
    return (
        int(value[1:])
        if isinstance(value, str) and re.fullmatch(r"P(?:[0-9]|1[0-4])", value)
        else None
    )


def _gate_checks(root, phase, disabled, add):
    """P0 is fixed: a caller cannot move the scan behind a future phase."""
    if phase != "P0":
        add(
            "ARCH_PHASE",
            "Only the current P0 policy is implemented; phase override cannot bypass it",
        )
    source = root / "plan/machine/ci-gates.yaml"
    try:
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError("gate source must be an in-repository regular file")
        data = yaml.safe_load(source.read_text())
        gates = data["gates"]
        if not isinstance(gates, list):
            raise ValueError("gates must be a list")
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        add("ARCH_GATES", str(exc), path="plan/machine/ci-gates.yaml")
        return []
    seen, rows = set(), []
    for gate in gates:
        if not isinstance(gate, dict) or not isinstance(gate.get("id"), str):
            add("ARCH_GATES", "malformed gate record")
            continue
        name = gate["id"]
        activation = _phase_number(gate.get("activation_phase"))
        if name in seen or activation is None:
            add("ARCH_GATES", "duplicate gate or invalid activation phase: " + name)
        seen.add(name)
        applicable = activation == 0 or name in P0_GATES
        if name in P0_GATES and activation != 0:
            add("ARCH_GATE_PHASE", "P0 gate cannot be deferred: " + name)
        if applicable and (gate.get("allow_failure") is not False or name in disabled):
            add(
                "ARCH_GATE_DISABLED",
                "Applicable hard gate cannot allow failure or be disabled: " + name,
            )
        rows.append(
            {
                "id": name,
                "activation_phase": gate.get("activation_phase"),
                "applicable": applicable,
                "disabled_requested": name in disabled,
                "result": "POLICY_CHECK_ONLY" if applicable else "NOT_APPLICABLE",
                "reason": "No CI execution is attested"
                if applicable
                else "Activation is after P0",
            }
        )
    for missing in sorted(P0_GATES - seen):
        add("ARCH_GATE_MISSING", "Required P0 gate is missing: " + missing)
    for unknown in sorted(set(disabled) - seen):
        add("ARCH_GATE_UNKNOWN", "Unknown gate switch: " + unknown)
    return rows


def _relative(name, level, module, is_package):
    package = module.split(".") if is_package else module.split(".")[:-1]
    if level > len(package):
        raise ValueError("relative import escapes production package")
    return ".".join(
        package[: len(package) - level + 1] + (name.split(".") if name else [])
    )


def _imports(tree, module, is_package, known, path, add):
    """Collect syntactic imports and recognized loader calls, including aliases.

    Bindings are over-approximated across scopes; candidate code is never run.
    A re-export remains a dependency edge, including for package initializers.
    """
    edges, bindings = [], defaultdict(set)
    nodes = list(ast.walk(tree))

    def edge(target, node, kind="import"):
        if target:
            edges.append(
                {
                    "source": module,
                    "target": target,
                    "path": path,
                    "line": node.lineno,
                    "kind": kind,
                }
            )

    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                edge(alias.name, node)
                bindings[alias.asname or alias.name.split(".")[0]].add(
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            try:
                base = (
                    _relative(node.module or "", node.level, module, is_package)
                    if node.level
                    else node.module or ""
                )
            except ValueError as exc:
                add("ARCH_RELATIVE", str(exc), path=path, line=node.lineno)
                continue
            edge(base, node)
            for alias in node.names:
                if alias.name == "*":
                    add(
                        "ARCH_DYNAMIC_UNKNOWN",
                        "Wildcard imports require explicit review",
                        path=path,
                        line=node.lineno,
                    )
                    continue
                target = base + "." + alias.name
                bindings[alias.asname or alias.name].add(target)
                if target in known:
                    edge(target, node, "from-submodule")

    def names(node):
        if isinstance(node, ast.Name):
            return bindings.get(node.id, {node.id})
        if isinstance(node, ast.Attribute):
            return {name + "." + node.attr for name in names(node.value)}
        if (
            isinstance(node, ast.Call)
            and names(node.func) & {"vars", "builtins.vars", "__builtins__.vars"}
            and len(node.args) == 1
        ):
            return {
                name + ".__dict__"
                for name in names(node.args[0])
                if name in {"builtins", "__builtins__", "importlib"}
            }
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            return {
                name.removesuffix(".__dict__") + "." + node.slice.value
                for name in names(node.value)
                if name.removesuffix(".__dict__")
                in {"builtins", "__builtins__", "importlib"}
            }
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
        ):
            if isinstance(node.args[1], ast.Constant) and isinstance(
                node.args[1].value, str
            ):
                return {name + "." + node.args[1].value for name in names(node.args[0])}
        return set()

    assignments = [
        node for node in nodes if isinstance(node, (ast.Assign, ast.AnnAssign))
    ]
    # Alias chains are finite. Unioning all bindings is conservative under scope
    # shadowing: uncertainty cannot erase an already observed unsafe origin.
    for _ in range(len(assignments) + 1):
        changed = False
        for node in assignments:
            if node.value is None:
                continue
            origin = names(node.value)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and origin - bindings[target.id]:
                    bindings[target.id].update(origin)
                    changed = True
        if not changed:
            break

    loaders = {
        "importlib.import_module",
        "__import__",
        "builtins.__import__",
        "__builtins__.__import__",
    }
    importer_state = ("sys.path", "sys.meta_path", "sys.path_hooks", "sys.modules")
    for node in nodes:
        if (
            isinstance(node, ast.Subscript)
            and any(
                name.removesuffix(".__dict__")
                in {"builtins", "__builtins__", "importlib"}
                for name in names(node.value)
            )
            and not names(node)
        ):
            add(
                "ARCH_DYNAMIC_UNKNOWN",
                "Computed reflective namespace key requires explicit review",
                path=path,
                line=node.lineno,
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
            targets = (
                node.targets
                if isinstance(node, (ast.Assign, ast.Delete))
                else [node.target]
            )
            for target in targets:
                candidate = (
                    target.value if isinstance(target, ast.Subscript) else target
                )
                if any(
                    any(_within(name, prefix) for prefix in importer_state)
                    for name in names(candidate)
                ):
                    add(
                        "ARCH_DYNAMIC_UNKNOWN",
                        "Importer state mutation cannot be statically certified",
                        path=path,
                        line=node.lineno,
                    )
        if not isinstance(node, ast.Call):
            continue
        called = names(node.func)
        if called & loaders:
            argument = (
                node.args[0]
                if node.args
                else next((k.value for k in node.keywords if k.arg == "name"), None)
            )
            if not isinstance(argument, ast.Constant) or not isinstance(
                argument.value, str
            ):
                add(
                    "ARCH_DYNAMIC_UNKNOWN",
                    "Dynamic import target is not a literal",
                    path=path,
                    line=node.lineno,
                )
                continue
            target = argument.value
            if not target:
                add(
                    "ARCH_DYNAMIC_UNKNOWN",
                    "Empty dynamic import target",
                    path=path,
                    line=node.lineno,
                )
                continue
            if target.startswith("."):
                package = (
                    node.args[1]
                    if len(node.args) > 1
                    else next(
                        (k.value for k in node.keywords if k.arg == "package"), None
                    )
                )
                if (
                    called != {"importlib.import_module"}
                    or not isinstance(package, ast.Constant)
                    or not isinstance(package.value, str)
                ):
                    add(
                        "ARCH_DYNAMIC_UNKNOWN",
                        "Relative dynamic import needs a literal package",
                        path=path,
                        line=node.lineno,
                    )
                    continue
                level = len(target) - len(target.lstrip("."))
                try:
                    target = _relative(target[level:], level, package.value, True)
                except ValueError as exc:
                    add("ARCH_RELATIVE", str(exc), path=path, line=node.lineno)
                    continue
            if (
                any(
                    k.arg == "level"
                    and not (isinstance(k.value, ast.Constant) and k.value.value == 0)
                    for k in node.keywords
                )
                or len(node.args) > 4
            ):
                add(
                    "ARCH_DYNAMIC_UNKNOWN",
                    "Relative __import__ semantics require explicit review",
                    path=path,
                    line=node.lineno,
                )
            edge(target, node, "literal-dynamic-import")
            if called & {
                "__import__",
                "builtins.__import__",
                "__builtins__.__import__",
            }:
                fromlist = (
                    node.args[3]
                    if len(node.args) > 3
                    else next(
                        (k.value for k in node.keywords if k.arg == "fromlist"), None
                    )
                )
                if fromlist is not None:
                    if not isinstance(fromlist, (ast.List, ast.Tuple)) or not all(
                        isinstance(item, ast.Constant)
                        and isinstance(item.value, str)
                        and item.value != "*"
                        for item in fromlist.elts
                    ):
                        add(
                            "ARCH_DYNAMIC_UNKNOWN",
                            "__import__ fromlist must be explicit literal names",
                            path=path,
                            line=node.lineno,
                        )
                    else:
                        for item in fromlist.elts:
                            candidate = target + "." + item.value
                            if candidate in known:
                                edge(candidate, node, "literal-dynamic-fromlist")
        if any(
            name
            in {
                "eval",
                "exec",
                "builtins.eval",
                "builtins.exec",
                "__builtins__.eval",
                "__builtins__.exec",
                "runpy.run_path",
                "runpy.run_module",
            }
            or (_within(name, "importlib") and name != "importlib.import_module")
            or name in {"pkgutil.get_loader", "pkgutil.resolve_name"}
            or any(_within(name, prefix) for prefix in importer_state)
            for name in called
        ):
            add(
                "ARCH_DYNAMIC_UNKNOWN",
                "Runtime code loading/importer mutation requires explicit review",
                path=path,
                line=node.lineno,
            )
        if isinstance(node.func, ast.Name) and node.func.id == "getattr" and node.args:
            origins = names(node.args[0])
            if any(
                name in {"importlib", "builtins", "__builtins__"} for name in origins
            ) and not names(node):
                add(
                    "ARCH_DYNAMIC_UNKNOWN",
                    "Computed reflective loader requires explicit review",
                    path=path,
                    line=node.lineno,
                )
    return edges


def _boundary(source, target):
    if target.split(".")[0] in HISTORICAL_ROOTS or any(
        part in {"archive", "convergence"} for part in target.split(".")
    ):
        return (
            "ARCH_ARCHIVE",
            "Production must not import historical, test, or tool code",
        )
    if _within(source, "anovel.domain"):
        for prefixes, label in (
            (PROVIDERS, "Provider"),
            (DATABASES, "database"),
            (WEB, "web"),
            (WORKFLOWS, "workflow"),
        ):
            if any(_within(target, prefix) for prefix in prefixes):
                return (
                    "ARCH_DOMAIN_DEPENDENCY",
                    "Domain depends on " + label + " implementation",
                )
        if target.startswith("anovel.") and not _within(target, "anovel.domain"):
            return (
                "ARCH_DOMAIN_LAYER",
                "Domain must use domain ports rather than application/adapter modules",
            )
        if target.split(".")[0] not in sys.stdlib_module_names | {"anovel", "pydantic"}:
            return (
                "ARCH_DOMAIN_UNKNOWN",
                "Domain third-party dependency is not in the reviewed allowlist",
            )
    if _within(target, REPOSITORY) and not any(
        _within(source, prefix)
        for prefix in (REPOSITORY, PUBLIC_COMMIT, "anovel.canon.projection")
    ):
        return (
            "ARCH_CANON_INTERNAL",
            "Canon repository is internal to repository, commit service, and projection",
        )
    if _within(target, PUBLIC_COMMIT) and not any(
        _within(source, prefix) for prefix in ("anovel.canon", "anovel.workflow")
    ):
        return (
            "ARCH_CANON_WRITE",
            "This module is not an authorized caller of the Canon commit service",
        )
    return None


def check_architecture(
    root: Path, *, package="src/anovel", phase="P0", disabled_gates=()
):
    """Return JSON-safe local observations; never import candidate source.

    ``root`` may be a temporary synthetic repository in tests. The fixed package
    location prevents callers from narrowing a real scan to a passing subtree.
    """
    root = Path(root).resolve()
    findings, files, modules, edges = [], [], {}, []

    def add(code, message, **context):
        item = {"code": code, "message": message, **context}
        if item not in findings:
            findings.append(item)

    gates = _gate_checks(root, phase, set(disabled_gates), add)
    if package != "src/anovel":
        add("ARCH_PACKAGE", "Production scan is fixed to the complete src/anovel tree")
    source = root / "src/anovel"
    if not source.is_dir() or source.is_symlink() or (root / "src").is_symlink():
        add(
            "ARCH_DISCOVERY",
            "Missing or symlinked production package root",
            path="src/anovel",
        )
    else:

        def walk_error(exc):
            add("ARCH_DISCOVERY", str(exc))

        for directory, directories, filenames in os.walk(
            source, followlinks=False, onerror=walk_error
        ):
            for name in list(directories):
                child = Path(directory) / name
                if child.is_symlink():
                    add(
                        "ARCH_PATH",
                        "Symlinked production directory is not scanned",
                        path=str(child.relative_to(root)),
                    )
                    directories.remove(name)
            for name in sorted(filenames):
                child = Path(directory) / name
                if not name.endswith(".py"):
                    continue
                relative = str(child.relative_to(root))
                if child.is_symlink() or not child.resolve().is_relative_to(source):
                    add(
                        "ARCH_PATH",
                        "Production source must not escape or alias the package tree",
                        path=relative,
                    )
                    continue
                parts = child.relative_to(source).with_suffix("").parts
                is_package = parts[-1] == "__init__"
                components = ("anovel", *(parts[:-1] if is_package else parts))
                module = ".".join(components)
                if not all(part.isidentifier() for part in components):
                    add(
                        "ARCH_MODULE",
                        "Python path has an invalid module identifier",
                        path=relative,
                    )
                try:
                    content = child.read_bytes()
                    tree = ast.parse(content, filename=relative)
                    files.append(
                        {
                            "path": relative,
                            "module": module,
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
                    if module in modules:
                        add(
                            "ARCH_MODULE",
                            "Ambiguous module/package name: " + module,
                            path=relative,
                        )
                    else:
                        modules[module] = (tree, is_package, relative)
                except (OSError, SyntaxError, ValueError) as exc:
                    add("ARCH_SOURCE", str(exc), path=relative)
    if not files:
        add("ARCH_EMPTY", "No parseable production Python sources were found")
    if "anovel" not in modules:
        add(
            "ARCH_DISCOVERY",
            "Installable package initializer src/anovel/__init__.py is required",
        )
    for module, (tree, is_package, path) in sorted(modules.items()):
        edges.extend(_imports(tree, module, is_package, modules, path, add))

    adjacency = defaultdict(list)
    complete_edges = list(edges)
    for edge in edges:
        # Importing a nested module executes its package initializers too.
        for count in range(1, len(edge["target"].split("."))):
            parent = ".".join(edge["target"].split(".")[:count])
            if parent in modules and modules[parent][1]:
                complete_edges.append(
                    {**edge, "target": parent, "kind": "package-initializer"}
                )
    for edge in complete_edges:
        adjacency[edge["source"]].append(edge)
    for source_module in sorted(modules):
        queue: deque[tuple[str, list[dict[str, str]]]] = deque([(source_module, [])])
        visited = set()
        while queue:
            current, chain = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in adjacency[current]:
                target = edge["target"]
                trace = [*chain, target]
                violation = _boundary(source_module, target)
                if violation:
                    code, message = violation
                    add(
                        code,
                        message,
                        path=modules[source_module][2],
                        line=edge["line"],
                        origin_path=edge["path"],
                        source=source_module,
                        target=target,
                        dependency_chain=[source_module, *trace],
                    )
                # A public service encapsulates storage for authorized callers;
                # ordinary module re-exports do not become such a boundary.
                approved_service = _within(target, PUBLIC_COMMIT) and _within(
                    source_module, "anovel.workflow"
                )
                if target in modules and not approved_service:
                    queue.append((target, trace))
    return {
        "record_type": "local_architecture_check",
        "status": "FAIL" if findings else "PASS",
        "root": str(root),
        "phase": "P0",
        "package": "src/anovel",
        "scope": "Static production-source discovery and import policy; synthetic fixtures are separate test evidence",
        "coverage": {
            "file_count": len(files),
            "module_count": len(modules),
            "bootstrap_only": set(modules) == {"anovel"},
        },
        "files": sorted(files, key=lambda row: row["path"]),
        "modules": sorted(modules),
        "edges": sorted(
            complete_edges,
            key=lambda row: (row["source"], row["line"], row["target"], row["kind"]),
        ),
        "gates": gates,
        "findings": findings,
        "limitations": [
            "No candidate module is imported or executed.",
            "Static imports, package re-exports and recognized literal loaders are inspected; arbitrary reflection is not proven safe.",
            "Aliases are conservatively combined across scopes; unresolved loader forms fail for review.",
            "P0 Canon caller policy is provisional static enforcement, not a P2 runtime/DB capability proof.",
            "Shared repository write access, remote CI provenance and protected permissions are not attested.",
        ],
    }
