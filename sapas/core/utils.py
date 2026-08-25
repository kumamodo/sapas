import yaml
from pathlib import Path


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
    return script_path

def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or {}