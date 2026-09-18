import sys
import yaml
from pathlib import Path


def reload_user_modules(workspace_root: Path, project_root: Path, script_dir: Path) -> None:
    """
    Unloads cached user modules from sys.modules so edits to helper scripts
    take effect immediately without needing to restart TUI.
    """
    targets = [
        str(workspace_root.resolve()).lower(),
        str(project_root.resolve()).lower(),
        str(script_dir.resolve()).lower()
    ]

    SYSTEM_PREFIXES = ("sapas", "rich", "textual", "yaml", "paramiko", "serial", "socket", "asyncio", "argparse")

    modules_to_unload = []
    for mod_name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if any(mod_name == prefix or mod_name.startswith(prefix + ".") for prefix in SYSTEM_PREFIXES):
            continue

        mod_file = getattr(mod, "__file__", None)
        if not mod_file or not isinstance(mod_file, str):
            continue

        mod_file_lower = str(Path(mod_file).resolve()).lower()
        if "site-packages" in mod_file_lower or "dist-packages" in mod_file_lower or "lib\\python" in mod_file_lower or "lib/python" in mod_file_lower:
            continue

        if any(mod_file_lower.startswith(t) for t in targets):
            modules_to_unload.append(mod_name)

    for mod_name in modules_to_unload:
        sys.modules.pop(mod_name, None)


def setup_sapas_sys_path(script_path: Path | str) -> None:
    """
    Automatically inject Sapas 3-tier search paths into sys.path:
    1. SCRIPT_DIR (e.g. Project/scripts/)
    2. PROJECT_ROOT (e.g. Project/)
    3. WORKSPACE_ROOT (e.g. Workspace/)
    """
    script_path_obj = Path(script_path).resolve()
    script_dir = script_path_obj.parent

    workspace_val = None
    project_val = None
    try:
        from sapas.runtime.runtime import ctx
        workspace_val = ctx.get("WORKSPACE_ROOT")
        project_val = ctx.get("PROJECT_NAME")
    except Exception:
        pass

    workspace_root = Path(workspace_val).resolve() if workspace_val else Path.cwd().resolve()
    project_root = (workspace_root / project_val).resolve() if (workspace_root and project_val) else script_dir.parent

    search_paths = []
    if script_dir.is_dir():
        search_paths.append(str(script_dir))
    if project_root.is_dir():
        search_paths.append(str(project_root))
    if workspace_root.is_dir():
        search_paths.append(str(workspace_root))

    for p in reversed(search_paths):
        if p not in sys.path:
            sys.path.insert(0, p)

    reload_user_modules(workspace_root, project_root, script_dir)


def resolve_user_script(script_name: str, project_name: str, workspace_root: Path | str | None = None) -> Path:
    script_name = Path(script_name).name
    if workspace_root is None:
        try:
            from sapas.runtime.runtime import ctx
            workspace_root = ctx.get('WORKSPACE_ROOT') if ctx else None
        except Exception:
            workspace_root = None
    workspace = Path(workspace_root) if workspace_root else Path.cwd()
    script_path = workspace / project_name / "scripts" / script_name
    script_path = script_path.resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"User script not found: {script_path}")
    
    setup_sapas_sys_path(script_path)
    return script_path

def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or {}