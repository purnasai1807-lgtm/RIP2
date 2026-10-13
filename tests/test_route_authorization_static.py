"""Dependency-light static policy checks for route authentication and authorization.

These checks supplement (and do not replace) runtime Flask authorization tests.
They intentionally parse the real route source so they can run before Flask is installed.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "app" / "routes.py"
SOURCE = ROUTES_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE, filename=str(ROUTES_PATH))

ROUTE_DECORATOR_METHODS = {"route", "get", "post", "put", "patch", "delete"}
PUBLIC_ROUTE_FUNCTIONS = {
    # Intentionally public infrastructure and authentication endpoints.
    "livez", "healthz", "index", "register", "verify_email",
    "resend_verification", "forgot_password", "reset_password", "auth_login",
}
ADMIN_ONLY_FUNCTIONS = {
    "admin_users", "admin_integrations", "admin_set_role", "admin_audit",
    "admin_impact_quality",
}
PRIVILEGED_FUNCTIONS = {
    "admin_users", "admin_integrations", "admin_set_role", "scenario_approval",
    "add_department", "add_course", "add_room", "add_timetable_entry",
    "import_official_timetable", "college_operations", "verify_attendance",
    "update_maintenance_status", "campus_services", "academic_services",
    "admin_audit", "admin_impact_quality",
}
SCENARIO_OWNER_FUNCTIONS = {
    "edit_scenario", "scenario_detail", "analyze_scenario", "simulate_scenario",
    "delete_scenario", "export_csv", "export_json",
}


def _route_functions() -> dict[str, tuple[ast.FunctionDef, list[str]]]:
    result = {}
    for node in ast.walk(TREE):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        paths = []
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "app":
                continue
            if decorator.func.attr not in ROUTE_DECORATOR_METHODS or not decorator.args:
                continue
            arg = decorator.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                paths.append(arg.value)
        if paths:
            result[node.name] = (node, paths)
    return result


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    return [child for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == name]


def _decorator_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    result = set()
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            result.add(target.id)
        elif isinstance(target, ast.Attribute):
            result.add(target.attr)
    return result


def test_every_route_is_explicitly_public_or_requires_login():
    routes = _route_functions()
    assert routes, "no application routes discovered in app/routes.py"
    names = set(routes)
    assert PUBLIC_ROUTE_FUNCTIONS <= names, f"public route names not found: {sorted(PUBLIC_ROUTE_FUNCTIONS - names)}"

    missing = []
    unexpected_public = []
    for name, (function, paths) in routes.items():
        protected = "login_required" in _decorator_names(function)
        if name not in PUBLIC_ROUTE_FUNCTIONS and not protected:
            missing.append((name, paths))
        if name in PUBLIC_ROUTE_FUNCTIONS and protected:
            unexpected_public.append((name, paths))
    assert not missing, f"routes missing @login_required: {missing}"
    assert not unexpected_public, f"public routes unexpectedly protected: {unexpected_public}"


def test_privileged_routes_have_role_checks_and_admin_routes_require_admin():
    routes = _route_functions()
    missing_role_checks = [name for name in sorted(PRIVILEGED_FUNCTIONS)
                           if name not in routes or not _calls_named(routes[name][0], "require_roles")]
    assert not missing_role_checks, f"privileged routes missing require_roles checks: {missing_role_checks}"

    missing_admin_literals = []
    for name in ADMIN_ONLY_FUNCTIONS:
        function = routes[name][0]
        calls = _calls_named(function, "require_roles")
        role_literals = {arg.value for call in calls for arg in call.args
                         if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
        if "admin" not in role_literals:
            missing_admin_literals.append(name)
    assert not missing_admin_literals, f"admin-only endpoints do not explicitly require admin: {missing_admin_literals}"


def test_sensitive_scenario_routes_keep_ownership_guard():
    routes = _route_functions()
    missing = []
    for name in SCENARIO_OWNER_FUNCTIONS - {"scenario_detail"}:
        if name not in routes or not _calls_named(routes[name][0], "owned_scenario"):
            missing.append(name)
    assert not missing, f"scenario routes missing owned_scenario guard: {missing}"

    # Detail and API handlers perform inline ownership checks rather than calling the helper.
    for name in ("scenario_detail", "api_get_scenario"):
        function = routes[name][0]
        identifiers = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
        assert "current_user" in identifiers and "scenario_id" in identifiers, \
            f"{name} must use user identity and the requested scenario ID"
        assert any(isinstance(node, ast.Compare) for node in ast.walk(function)), \
            f"{name} must retain its owner/role comparison"


def test_every_post_request_is_covered_by_global_csrf_guard():
    hooks = [node for node in ast.walk(TREE)
             if isinstance(node, ast.FunctionDef) and node.name == "protect_post_requests"]
    assert len(hooks) == 1, "expected one global POST CSRF guard"
    hook = hooks[0]
    names = {node.id for node in ast.walk(hook) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(hook) if isinstance(node, ast.Attribute)}
    constants = {node.value for node in ast.walk(hook) if isinstance(node, ast.Constant)}
    assert "request" in names and "session" in names and "secrets" in names
    assert "method" in attributes and "compare_digest" in attributes
    assert "_csrf_token" in constants and "POST" in constants
