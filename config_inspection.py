"""Static analysis for configuration precedence inspection."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from sandbox import TRUNCATION_NOTE, SandboxError, get_workspace

_MAX_CONFIG_LAYERS = 20
_MAX_CONFIG_CONDITION_CHARS = 200
_MAX_CONFIG_PRECEDENCE_OUTPUT_CHARS = 2_400
_PAIR_SIZE = 2
_UNSUPPORTED_CONTROL_FLOW = (ast.AsyncFor, ast.AsyncWith, ast.BoolOp, ast.For, ast.IfExp,
                             ast.Lambda, ast.ListComp, ast.Match, ast.SetComp, ast.Try,
                             ast.TryStar, ast.While, ast.With, ast.GeneratorExp)


def _module_string_constants(module: ast.Module) -> dict[str, str]:
    """Collect simple top-level string constants without evaluating source."""
    constants: dict[str, str] = {}
    for statement in module.body:
        if isinstance(statement, ast.AnnAssign):
            targets = [statement.target] if isinstance(statement.target, ast.Name) else []
            value = statement.value
        elif isinstance(statement, ast.Assign):
            targets = [target for target in statement.targets if isinstance(target, ast.Name)]
            value = statement.value
        else:
            continue

        for target in targets:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                constants[target.id] = value.value
            else:
                constants.pop(target.id, None)
    return constants


def _static_layer_label(expression: ast.expr, constants: dict[str, str]) -> str:
    """Resolve literals/constants; retain simple f-string names symbolically."""
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    if not isinstance(expression, ast.JoinedStr):
        raise TypeError("layer label is not a string literal or a simple f-string")
    parts: list[str] = []
    for part in expression.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            parts.append(part.value)
        elif (
            isinstance(part, ast.FormattedValue)
            and isinstance(part.value, ast.Name)
            and part.conversion == -1
            and part.format_spec is None
        ):
            name = part.value.id
            parts.append(constants.get(name, f"{{{name}}}"))
        else:
            raise ValueError("layer label contains an unsupported expression")
    return "".join(parts)


def _name_pair(target: ast.expr) -> tuple[str, str] | None:
    if isinstance(target, ast.Tuple) and len(target.elts) == _PAIR_SIZE:
        first, second = target.elts
        if isinstance(first, ast.Name) and isinstance(second, ast.Name):
            return first.id, second.id
    return None


def _iterates_name(expression: ast.expr, name: str) -> bool:
    if isinstance(expression, ast.Name):
        return expression.id == name
    return (
        isinstance(expression, ast.Call)
        and not expression.args
        and not expression.keywords
        and isinstance(expression.func, ast.Attribute)
        and expression.func.attr == "items"
        and isinstance(expression.func.value, ast.Name)
        and expression.func.value.id == name
    )


def _append_conditions(
    call: ast.AST,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    parents: dict[ast.AST, ast.AST],
    source: str,
) -> list[str]:
    conditions: list[str] = []
    node: ast.AST = call
    while node is not function:
        parent = parents.get(node)
        if parent is None:
            raise ValueError("could not determine the layer append's control flow")
        if isinstance(parent, ast.If):
            test = ast.get_source_segment(source, parent.test) or ast.unparse(parent.test)
            test = " ".join(test.split())
            if len(test) > _MAX_CONFIG_CONDITION_CHARS:
                raise ValueError("conditional guard is too long to report safely")
            branch = "if" if node in parent.body else "else" if node in parent.orelse else ""
            if not branch:
                raise ValueError("layer append appears inside an unsupported condition")
            conditions.append(f"{branch} {test}" if branch == "if" else f"else (not {test})")
        elif isinstance(parent, _UNSUPPORTED_CONTROL_FLOW):
            raise TypeError("layer append is nested in unsupported control flow")
        elif isinstance(parent, ast.FunctionDef) and parent is not function:
            raise ValueError("nested functions inside resolve() are unsupported")
        node = parent
    conditions.reverse()
    return conditions


def _is_merge_assignment(
    statement: ast.Assign, merged_name: str, field_name: str, value_name: str
) -> bool:
    if (
        len(statement.targets) != 1
        or not isinstance(statement.value, ast.Name)
        or statement.value.id != value_name
    ):
        return False
    target = statement.targets[0]
    return (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and target.value.id == merged_name
        and isinstance(target.slice, ast.Name)
        and target.slice.id == field_name
    )


def _function_nodes(root: ast.AST) -> list[ast.AST]:
    return list(ast.walk(root))


def _parent_map(root: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _named_assignment(
    statement: ast.stmt, name: str
) -> tuple[ast.expr, ast.expr] | None:
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == name
    ):
        return statement.targets[0], statement.value
    if (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == name
        and statement.value is not None
    ):
        return statement.target, statement.value
    return None


def _resolve_function(module: ast.Module) -> ast.FunctionDef:
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    ]
    if len(functions) != 1:
        raise ValueError("expected exactly one top-level resolve() function")
    return functions[0]


def _validate_layer_mutations(
    function: ast.FunctionDef,
    parents: dict[ast.AST, ast.AST],
    initializer: ast.Assign | ast.AnnAssign,
    append_calls: list[ast.Call],
    outer: ast.For,
) -> None:
    initializer_target, _ = _named_assignment(initializer, "layers") or (None, None)
    if initializer_target is None:
        raise ValueError("layers must be initialized as a simple local name")
    if initializer.lineno >= append_calls[0].lineno or initializer.lineno >= outer.lineno:
        raise ValueError("layers must be initialized before appends and merge")
    names = (
        node
        for node in _function_nodes(function)
        if isinstance(node, ast.Name) and node.id == "layers"
    )
    for name in names:
        parent = parents.get(name)
        if parent is initializer and name is initializer_target:
            continue
        if parent is outer and name is outer.iter and isinstance(name.ctx, ast.Load):
            continue
        if (
            isinstance(parent, ast.Attribute)
            and parent.attr == "append"
            and parent.value is name
            and isinstance(parents.get(parent), ast.Call)
            and parents[parent] in append_calls
        ):
            continue
        raise ValueError("layers may only be initialized empty, appended, then iterated")


def _validate_merged_mutations(
    function: ast.FunctionDef,
    assignment: ast.Assign,
    initializer: ast.Assign | ast.AnnAssign,
    settings_call: ast.Call | None,
) -> None:
    initializer_target, _ = _named_assignment(initializer, "merged") or (None, None)
    if initializer_target is None:
        raise ValueError("merged must be initialized as a simple local name")
    parents = _parent_map(function)
    names = (
        node
        for node in _function_nodes(function)
        if isinstance(node, ast.Name) and node.id == "merged"
    )
    for name in names:
        parent = parents.get(name)
        if parent is initializer and name is initializer_target:
            continue
        if isinstance(parent, ast.Return) and isinstance(name.ctx, ast.Load):
            continue
        if (
            settings_call is not None
            and isinstance(parent, ast.keyword)
            and parent.arg is None
            and parent.value is name
            and parents.get(parent) is settings_call
        ):
            continue
        target = assignment.targets[0]
        if (
            isinstance(target, ast.Subscript)
            and parent is target
            and target.value is name
            and isinstance(name.ctx, ast.Load)
        ):
            continue
        raise ValueError("merged may only be initialized empty, overwritten by loop, and returned")


def _validate_merge_loops(
    function: ast.FunctionDef,
    outer: ast.For,
    inner: ast.For,
    assignment: ast.Assign,
) -> None:
    if outer not in function.body or outer.orelse or inner not in outer.body or inner.orelse:
        raise ValueError("merge loops must be unconditional canonical loops")
    if assignment not in inner.body:
        raise ValueError("merged[field] assignment must be unconditional in the inner loop")
    if (
        outer.body != [inner]
        or inner.body.count(assignment) != 1
        or any(not isinstance(statement, ast.Assign) for statement in inner.body)
    ):
        raise ValueError("merge loops contain unsupported statements")
    if any(
        isinstance(node, ast.If | ast.Break | ast.Continue | ast.Match | ast.Try | ast.TryStar)
        for node in _function_nodes(outer)
    ):
        raise ValueError("conditional flow inside merge loops is unsupported")


def _validate_exit_paths(
    function: ast.FunctionDef,
    outer: ast.For,
    append_calls: list[ast.Call],
    source: str,
) -> list[str]:
    outer_end = outer.end_lineno or outer.lineno
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    if (
        len(returns) != 1
        or not function.body
        or function.body[-1] is not returns[0]
        or returns[0].lineno <= outer_end
    ):
        raise ValueError("resolve() must have one final return after the merge completes")

    parents = _parent_map(function)
    abort_rows: list[str] = []
    for node in (item for item in ast.walk(function) if isinstance(item, ast.Raise)):
        if node.lineno >= outer.lineno:
            if node.lineno <= outer_end:
                raise ValueError("raise inside merge loops is unsupported")
            continue
        if not _is_profile_abort(node, parents, append_calls):
            raise ValueError(
                "only the guarded missing-profile validation raise is supported before merge"
            )
        conditions = _append_conditions(node, function, parents, source)
        if not conditions:
            raise ValueError("pre-merge raise must be under a static guard")
        branch_path = _branch_path(node, parents)
        for append in append_calls:
            if (append.lineno, append.col_offset) >= (node.lineno, node.col_offset):
                continue
            if _paths_can_overlap(branch_path, _branch_path(append, parents)):
                raise ValueError("pre-merge raise may follow a layer append on the same path")
        abort_rows.append(
            f"line {node.lineno}: when file_path is None and profile is set, "
            f"raises {_raised_exception_name(node)} and returns no resolved settings"
        )
    return abort_rows


def _raised_exception_name(node: ast.Raise) -> str:
    exception = node.exc
    if isinstance(exception, ast.Call):
        exception = exception.func
    if isinstance(exception, ast.Name):
        return exception.id
    return "an error"


def _branch_path(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> dict[ast.If, str]:
    branches: dict[ast.If, str] = {}
    current = node
    while (parent := parents.get(current)) is not None:
        if isinstance(parent, ast.If):
            if current in parent.body:
                branches[parent] = "body"
            elif current in parent.orelse:
                branches[parent] = "orelse"
        current = parent
    return branches


def _paths_can_overlap(left: dict[ast.If, str], right: dict[ast.If, str]) -> bool:
    return all(left[branch] == right[branch] for branch in left.keys() & right.keys())


def _is_profile_abort(
    node: ast.Raise,
    parents: dict[ast.AST, ast.AST],
    append_calls: list[ast.Call],
) -> bool:
    current: ast.AST = node
    while (parent := parents.get(current)) is not None:
        if (
            isinstance(parent, ast.If)
            and current in parent.orelse
            and ast.unparse(parent.test) == "file_path is not None"
            and any(
                call in ast.walk(statement)
                for statement in parent.body
                for call in append_calls
            )
            and any(
                isinstance(candidate, ast.If)
                and ast.unparse(candidate.test) == "profile"
                and node in ast.walk(candidate)
                for candidate in parent.orelse
            )
        ):
            return True
        current = parent
    return False


def _validate_static_calls(function: ast.FunctionDef) -> None:
    allowed_calls = {
        "dict", "_from_env", "layers.append", "_reject_unknown", "Settings",
        "settings.model_copy", "Path.cwd", "read_config_file", "_section",
        "discovered.is_file", "_profile", "read_env_file", "values.items",
        "(cli or {}).items",
        "sources.get", "sources.setdefault", "settings.log_level.upper",
        "ConfigError", "ValidationError", "ValueError", "exc.errors", "str",
        "'; '.join", "', '.join", "'.'.join",
    }
    nodes = list(ast.walk(function))
    for node in nodes:
        if isinstance(node, ast.Import | ast.ImportFrom):
            raise TypeError("imports inside resolve() are unsupported")
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            raise ValueError("__builtins__ access is unsupported")
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name | ast.Attribute):
            raise TypeError("dynamic callable expressions are unsupported")
        callable_name = ast.unparse(node.func)
        if callable_name not in allowed_calls:
            raise ValueError(f"unsupported call in resolve(): {callable_name}")


@dataclass(frozen=True)
class _LayerRowContext:
    function: ast.FunctionDef
    parents: dict[ast.AST, ast.AST]
    source: str
    constants: dict[str, str]


def _layer_row(index: int, call: ast.Call, context: _LayerRowContext) -> str:
    if not isinstance(context.parents.get(call), ast.Expr):
        raise TypeError("layers.append() must be a standalone statement")
    if len(call.args) != 1 or call.keywords or not isinstance(call.args[0], ast.Tuple):
        raise ValueError("layers.append() must receive one (label, value) tuple")
    pair = call.args[0].elts
    if len(pair) != _PAIR_SIZE:
        raise ValueError("layer tuple must contain exactly a label and a value")
    label = _static_layer_label(pair[0], context.constants)
    if not label or len(label) > _MAX_CONFIG_CONDITION_CHARS:
        raise ValueError("layer label is empty or too long to report safely")
    conditions = _append_conditions(
        call, context.function, context.parents, context.source
    )
    condition_text = "; ".join(conditions) if conditions else "unconditional"
    if label.casefold() == "environment":
        kind = "process environment"
    elif label.casefold().endswith(" file") or label.casefold().startswith("file:"):
        kind = "file layer"
    else:
        kind = "configuration layer"
    return f"{index}. {label!r} ({kind}), line {call.lineno}; {condition_text}"


def _layer_rows(function: ast.FunctionDef, source: str, constants: dict[str, str]) -> list[str]:
    parents = _parent_map(function)
    initializers: list[ast.Assign | ast.AnnAssign] = [
        statement
        for statement in function.body
        if isinstance(statement, ast.Assign | ast.AnnAssign)
        and _named_assignment(statement, "layers") is not None
    ]
    initializer_pair = (
        _named_assignment(initializers[0], "layers") if len(initializers) == 1 else None
    )
    initializer_target = initializer_pair[0] if initializer_pair is not None else None
    initializer_value = initializer_pair[1] if initializer_pair is not None else None
    if (
        len(initializers) != 1
        or not isinstance(initializer_value, ast.List)
        or initializer_value.elts
        or initializer_target is None
    ):
        raise ValueError("layers must be initialized once as an empty list")
    initializer = initializers[0]

    append_calls = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append" and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "layers"
    ]
    append_calls.sort(key=lambda node: (node.lineno, node.col_offset))
    if not append_calls:
        raise ValueError("resolve() has no static layers.append((label, value)) entries")
    if len(append_calls) > _MAX_CONFIG_LAYERS:
        raise ValueError(f"resolve() exceeds the {_MAX_CONFIG_LAYERS}-layer inspection limit")

    outer_loops = [
        statement
        for statement in function.body
        if isinstance(statement, ast.For)
        and isinstance(statement.iter, ast.Name)
        and statement.iter.id == "layers"
        and _name_pair(statement.target) is not None
    ]
    if len(outer_loops) != 1:
        raise ValueError("expected one top-level merge loop over layers")
    outer = outer_loops[0]
    if any(call.lineno >= outer.lineno for call in append_calls):
        raise ValueError("all layer appends must precede the merge loop")
    _validate_layer_mutations(function, parents, initializer, append_calls, outer)

    row_context = _LayerRowContext(function, parents, source, constants)
    return [
        _layer_row(index, call, row_context)
        for index, call in enumerate(append_calls, start=1)
    ]


def _merge_rows(function: ast.FunctionDef, source: str) -> list[str]:
    append_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "layers"
    ]
    outer_loops: list[ast.For] = [
        node for node in _function_nodes(function)
        if isinstance(node, ast.For)
        if isinstance(node.iter, ast.Name)
        and node.iter.id == "layers"
        and _name_pair(node.target) is not None
    ]
    if len(outer_loops) != 1:
        raise ValueError("expected one for-pair loop over layers")
    outer = outer_loops[0]
    layer_names = _name_pair(outer.target)
    if layer_names is None:
        raise ValueError("the layer loop target must be a two-name tuple")
    layer_name, values_name = layer_names

    inner_loops: list[ast.For] = [
        node for node in _function_nodes(outer)
        if isinstance(node, ast.For)
        if node is not outer
        and _iterates_name(node.iter, values_name)
        and _name_pair(node.target) is not None
    ]
    if len(inner_loops) != 1:
        raise ValueError("expected one nested field/value loop over each layer")
    inner = inner_loops[0]
    if outer not in function.body or outer.orelse or inner not in outer.body or inner.orelse:
        raise ValueError("merge loops must be unconditional canonical loops")
    field_names = _name_pair(inner.target)
    if field_names is None:
        raise ValueError("the inner loop target must be a two-name tuple")
    field_name, value_name = field_names

    merge_assignments: list[ast.Assign] = [
        node for node in _function_nodes(inner)
        if isinstance(node, ast.Assign)
        if _is_merge_assignment(node, "merged", field_name, value_name)
    ]
    if len(merge_assignments) != 1:
        raise ValueError("expected one merged[field] = value assignment in the nested loop")
    assignment = merge_assignments[0]
    initializers: list[ast.Assign | ast.AnnAssign] = [
        statement
        for statement in function.body
        if isinstance(statement, ast.Assign | ast.AnnAssign)
        and _named_assignment(statement, "merged") is not None
    ]
    initializer_pair = (
        _named_assignment(initializers[0], "merged") if len(initializers) == 1 else None
    )
    initializer_target = initializer_pair[0] if initializer_pair is not None else None
    initializer_value = initializer_pair[1] if initializer_pair is not None else None
    if (
        len(initializers) != 1
        or not isinstance(initializer_value, ast.Dict)
        or initializer_value.keys
        or initializer_value.values
        or initializers[0].lineno >= outer.lineno
        or initializer_target is None
    ):
        raise ValueError("merged must start as an empty dictionary before the loops")
    _validate_merge_loops(function, outer, inner, assignment)
    abort_rows = _validate_exit_paths(function, outer, append_calls, source)

    final_return = next(node for node in ast.walk(function) if isinstance(node, ast.Return))
    settings_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Settings"
        and node.lineno > (outer.end_lineno or outer.lineno)
        and (node.end_lineno or node.lineno) < final_return.lineno
    ]
    if isinstance(final_return.value, ast.Name) and final_return.value.id == "merged":
        settings_row: list[str] = []
        settings_call = None
    elif (
        len(settings_calls) == 1
        and not settings_calls[0].args
        and any(
            keyword.arg is None
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "merged"
            for keyword in settings_calls[0].keywords
        )
    ):
        settings_call = settings_calls[0]
        settings_row = [
            f"line {settings_calls[0].lineno}: Settings(**merged) consumes merged after the loop"
        ]
    else:
        raise ValueError("final return must use merged directly or through Settings(**merged)")
    _validate_merged_mutations(function, assignment, initializers[0], settings_call)

    return [
        "Merge evidence:",
        f"line {outer.lineno}: for {layer_name}, {values_name} in layers",
        f"line {inner.lineno}: for {field_name}, {value_name} in {ast.unparse(inner.iter)}",
        f"line {assignment.lineno}: merged[{field_name}] = {value_name}",
        (
            "The loops preserve append order; assigning the same dictionary key again "
            "means a later layer overrides an earlier value."
        ),
        *settings_row,
        *abort_rows,
    ]


def _extract_config_precedence(source: str) -> str:
    """Describe static layer appends and the nested overwrite loop in resolve()."""
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, "lineno", None)
        suffix = f" at line {line}" if line is not None else ""
        raise ValueError(f"malformed Python source{suffix}") from exc

    function = _resolve_function(module)
    _validate_static_calls(function)
    lines = [
        "Configuration layers in append order:",
        *_layer_rows(function, source, _module_string_constants(module)),
        *_merge_rows(function, source),
    ]
    rendered = "\n".join(lines)
    if len(rendered) > _MAX_CONFIG_PRECEDENCE_OUTPUT_CHARS:
        raise ValueError("precedence report exceeds its output limit")
    return rendered


def inspect_config_precedence(path: str) -> str:
    """Statically inspect a workspace Python resolver without executing it."""
    workspace = get_workspace()
    try:
        admitted = workspace.resolve(path)
        source = workspace.read_text(workspace.display(admitted))
    except SandboxError as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: could not read {path!r}: {exc.strerror or exc}"

    truncation_marker = TRUNCATION_NOTE.format(limit=workspace.max_read_chars)
    if truncation_marker in source:
        return f"Error: {workspace.display(admitted)} is too large to inspect completely."
    try:
        report = _extract_config_precedence(source)
    except (TypeError, ValueError) as exc:
        return f"Error: cannot inspect config precedence in {workspace.display(admitted)}: {exc}."
    return f"{workspace.display(admitted)}:\n{report}"
