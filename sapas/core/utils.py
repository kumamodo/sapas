import yaml
from pathlib import Path


def resolve_user_script(script_name: str, project_name: str) -> Path:
    script_name = Path(script_name).name
    workspace = Path.cwd()
    script_path = workspace / project_name / "scripts" / script_name
    script_path = script_path.resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"User script not found: {script_path}")
    return script_path

def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or {}