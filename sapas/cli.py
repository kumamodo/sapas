import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

import time
from datetime import datetime
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich.columns import Columns

from sapas.runtime.context import ExecutionContext
import sapas.runtime.runtime as rt
from sapas.core.runner import Runner
from sapas.core.utils import load_yaml


console = Console()
def interpolate_rgb(start_rgb, end_rgb, fraction):
    r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * fraction)
    g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * fraction)
    b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * fraction)
    return (r, g, b)

def get_gradient_block(text: str, start_rgb: tuple, end_rgb: tuple, bold=False):
    gradient_text = Text()
    num_chars = len(text)
    if num_chars <= 1:
        color = f"rgb({start_rgb[0]},{start_rgb[1]},{start_rgb[2]})"
        gradient_text.append(text, style=f"{color} bold" if bold else color)
        return gradient_text

    for i, char in enumerate(text):
        fraction = i / (num_chars - 1)
        r, g, b = interpolate_rgb(start_rgb, end_rgb, fraction)
        color = f"rgb({r},{g},{b})"
        style = f"{color} bold" if bold else color
        gradient_text.append(char, style=style)
    return gradient_text

def draw_welcome_screen(project_name: str, station_name: str, test_flow: str):
    """
    Render the sapas welcome screen.
    """
    ascii_logo_blocks = [
        " ██████    █████   ██████    █████    ██████ ",
        "██        ██   ██  ██   ██  ██   ██  ██      ",
        " █████    ███████  ██████   ███████   █████  ",
        "     ██   ██   ██  ██       ██   ██       ██ ",
        "██████    ██   ██  ██       ██   ██  ██████  "
    ]
    # hotpink
    logo_start_color = (255, 105, 180)
    # lightskyblue
    logo_end_color = (135, 206, 250)

    gradient_logo = Text()
    for row in ascii_logo_blocks:
        gradient_logo.append(get_gradient_block(row, logo_start_color, logo_end_color))
        gradient_logo.append("\n")

    project_color_start = (200, 200, 250)
    project_color_end = (180, 230, 250)
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Set the tag width.
    L_WIDTH = 12

    project_info = Text()
    # project_info.append("\n")
    project_info.append("─── ENVIRONMENT ───".center(L_WIDTH + 15), style="dim cyan bold")
    project_info.append("\n")

    project_info.append(get_gradient_block(
        f" {'PROJECT'.ljust(L_WIDTH)}: {project_name}", project_color_start, project_color_end, bold=True
    ))
    project_info.append("\n")
    project_info.append(get_gradient_block(
        f" {'STATION'.ljust(L_WIDTH)}: {station_name}", project_color_start, project_color_end
    ))
    project_info.append("\n")
    project_info.append(get_gradient_block(
        f" {'TEST FLOW'.ljust(L_WIDTH)}: {test_flow}", project_color_start, project_color_end
    ))
    project_info.append("\n")
    project_info.append(f" {'START TIME'.ljust(L_WIDTH)}: {current_time}", style="dim white")

    content = Columns([gradient_logo, Align.right(project_info)], expand=True)

    welcome_panel = Panel(
        content,
        title="[cyan][ SAPAS Framework][/]",
        border_style="magenta",
        padding=(1, 4),
        expand=False
    )

    console.print("\n")
    console.print(welcome_panel)
    console.print("\n")
    time.sleep(0.5)

def find_site_infra(start_dir: Path) -> tuple[Path | None, dict]:
    """
    Search upwards from start_dir for site_infra.yaml.
    Returns (infra_root_path, env_dict).
    """
    curr = start_dir.resolve()
    while True:
        candidate = curr / "site_infra.yaml"
        if candidate.is_file():
            return curr, load_yaml(candidate)
        if curr.parent == curr:
            break
        curr = curr.parent
    return None, {}

def setup_context(args):
    # [Environment Initialization] Responsible for converting all YAML files
    # into a unified context and wiring it into the global rt.

    curr_dir = Path.cwd().resolve()
    infra_root, env = find_site_infra(curr_dir)

    # Determine the project and test station (priority: CLI arguments > site_infra.yaml).
    project_name = args.project or env.get("PROJECT_NAME")
    station_name = args.station or env.get("STATION_NAME")

    if not project_name or not station_name:
        print("\033[91m[Error] Project or Station not specified!\033[0m")
        print("Please specify via CLI arguments (--project <Project> --station <Station>) or define them in site_infra.yaml.")
        sys.exit(1)

    # Smart Workspace & Project Directory Resolution
    if infra_root:
        workspace_root = infra_root
        if curr_dir == workspace_root / project_name or curr_dir.name == project_name:
            project_dir = curr_dir
        else:
            project_dir = workspace_root / project_name
    else:
        if (curr_dir / "stations").is_dir() or curr_dir.name == project_name:
            project_dir = curr_dir
            workspace_root = curr_dir.parent
        else:
            workspace_root = curr_dir
            project_dir = workspace_root / project_name

    # Define the path and check whether it exists.
    station_path = project_dir / "stations" / f"{station_name}" / "station.yaml"
    project_config_path = project_dir / "configs" / "project.yaml"

    if not station_path.exists():
        print(f"\033[91m[Error] Station config not found: {station_path}\033[0m")
        print(f"Please check if project '{project_name}' and station '{station_name}' exist in '{workspace_root}'.")
        sys.exit(1)

    station_var = load_yaml(station_path)
    project_var = load_yaml(project_config_path) if project_config_path.exists() else {}

    # Create a single unified Context and connect it to the global rt registry/bus.
    context = ExecutionContext(station_var, project_var, env_cfg=env)
    context.set('WORKSPACE_ROOT', str(workspace_root))
    context.set('PROJECT_NAME', project_name)
    context.set('STATION_NAME', station_name)

    # Remote safety & quality guard: Force ENABLE_SHOPFLOOR to False during remote SSH or maintenance lock
    is_remote_session = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION"))
    from sapas.guard.lock_manager import is_locked
    if is_remote_session or is_locked():
        if context.get("ENABLE_SHOPFLOOR", False):
            context.set("ENABLE_SHOPFLOOR", False)
            console.print("[bold yellow][SECURITY] Remote session or Station Guard lock active! ENABLE_SHOPFLOOR is forced to FALSE to protect shopfloor integrity.[/]")

    # Initialize the global runtime.
    rt.init(context)
    return context


def print_guard_help() -> None:
    help_text = """
[bold cyan]Sapas Station Guard[/] - Remote Maintenance Lock & Station Protection

[bold]Usage:[/]
  sapas guard <command> \[options]

[bold]Commands:[/]
  [bold green]lock[/] "message"      Engage station maintenance lock (blocks local testing & alerts desktop)
  [bold green]unlock[/]              Release station maintenance lock (restores normal operations)
  [bold green]status[/]              Check guard daemon status and active lock details
  [bold green]install[/]             Install Station Guard into Windows Startup for auto-protection
  [bold green]reinstall[/]           Reset state and reinstall Station Guard to Windows Startup
  [bold green]uninstall[/]           Remove Station Guard from Windows Startup and stop background process

[bold]Examples:[/]
  sapas guard lock "Replacing RF cable"
  sapas guard unlock
  sapas guard status
  sapas guard install
  sapas guard reinstall
"""
    console.print(help_text.strip())


def handle_guard_cli(argv: list[str]) -> None:
    """Handles sapas guard subcommands (lock, unlock, status, install, reinstall, uninstall)."""
    if not argv or argv[0].lower() in ("-h", "--help", "help"):
        print_guard_help()
        sys.exit(0)

    subcmd = argv[0].lower()

    if subcmd == "lock":
        lock_args = argv[1:]
        msg = ""
        if lock_args:
            if lock_args[0] in ("-m", "--message") and len(lock_args) > 1:
                msg = " ".join(lock_args[1:]).strip()
            else:
                msg = " ".join(lock_args).strip()

        from sapas.guard.installer import get_daemon_pid

        # Fail fast: If station guard daemon is NOT running on the station desktop, do NOT claim it is locked!
        daemon_pid = get_daemon_pid()
        if not daemon_pid:
            is_remote_session = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION"))
            if is_remote_session:
                explanation = (
                    "[bold red][!] [ERROR] CANNOT ENGAGE STATION GUARD LOCK![/]\n\n"
                    "The Station Guard daemon is NOT running on the interactive desktop session.\n\n"
                    "[bold yellow]Technical Note:[reset]\n"
                    "  Due to Windows Session Isolation (Session 0 boundary), GUI screens cannot be\n"
                    "  spawned headlessly across remote SSH sessions without an active desktop login.\n\n"
                    "[bold white]Remedy Options:[reset]\n\n"
                    "  [bold cyan]• Option 1: On-site Setup (Instant / No Reboot)[reset]\n"
                    "    Ask an on-site engineer to run locally on the station PC:\n"
                    "      [bold green]sapas guard install[reset]\n\n"
                    "  [bold cyan]• Option 2: Remote Setup via SSH (Requires Station Reboot)[reset]\n"
                    "    1. Run installation in this SSH session:\n"
                    "       [bold green]sapas guard install[reset]\n"
                    "    2. Reboot the station PC remotely:\n"
                    "       [bold green]shutdown /r /t 0[reset]\n"
                    "       [dim](or ask on-site personnel to log in to start the desktop session)[/]\n"
                )
            else:
                explanation = (
                    "[bold red][!] [ERROR] CANNOT ENGAGE STATION GUARD LOCK![/]\n\n"
                    "[white]The Station Guard background daemon is not running on this PC.[/]\n\n"
                    "[bold bright_yellow]To activate Station Guard on this machine, run:[reset]\n"
                    "  [bold bright_green]sapas guard install[reset]\n"
                )

            console.print(Panel(
                Text.from_markup(explanation),
                title="Station Guard Interlock Error",
                border_style="red"
            ))
            sys.exit(1)

        from sapas.guard.lock_manager import acquire_lock
        data = acquire_lock(msg)

        console.print(Panel(
            Text.assemble(
                ("[!] [LOCKED] Station maintenance lock engaged!\n\n", "bold red"),
                ("  Message   : ", "bold yellow"), (f"{data['message']}\n", "white"),
                ("  Source IP : ", "bold cyan"), (f"{data['ip']}\n", "bright_cyan"),
                ("  Lock Time : ", "bold"), (f"{data['time']}\n", "dim"),
            ),
            title="Sapas Station Guard",
            border_style="red"
        ))
        sys.exit(0)

    elif subcmd == "unlock":
        from sapas.guard.lock_manager import release_lock, is_locked, clear_override_event
        was_locked = is_locked()
        released = release_lock()
        cleared_override = clear_override_event()
        if released or was_locked or cleared_override:
            console.print("[bold green][OK] [UNLOCKED] Station maintenance lock and emergency override released. Normal operations restored.[/]")
        else:
            console.print("[yellow][Notice] Station was not locked.[/]")
        sys.exit(0)

    elif subcmd in ("status", "--status"):
        from sapas.guard.installer import get_status
        st = get_status()
        console.print(Panel(
            Text.assemble(
                ("Station Guard Status:\n", "bold"),
                ("  Startup Auto-Run : ", "bold"), (("Installed" if st["installed"] else "Not installed") + "\n", "green" if st["installed"] else "yellow"),
                ("  Daemon Process   : ", "bold"), ((f"Running (PID {st['daemon_pid']})" if st["running"] else "Stopped") + "\n", "green" if st["running"] else "dim"),
                ("  Lock Status      : ", "bold"), (("LOCKED" if st["locked"] else "IDLE (Unlocked)") + "\n", "bold red" if st["locked"] else "green"),
                ("  Startup Path     : ", "dim"), (f"{st['vbs_path']}\n", "dim"),
            ),
            title="Sapas Guard Service",
            border_style="cyan"
        ))
        if st["locked"] and st.get("lock_info"):
            info = st["lock_info"]
            console.print(f"  [red]Active Lock: '{info.get('message')}' from {info.get('ip')} at {info.get('time')}[/]")
        from sapas.guard.lock_manager import get_override_event
        ov = get_override_event()
        if ov:
            console.print(f"  [bold white on red][!] EMERGENCY OVERRIDE ACTIVE:[/] {ov.get('reason')} at {ov.get('time')}")
            console.print("      [yellow]Remote execution is temporarily frozen until 'sapas guard lock' is re-engaged.[/]")
        sys.exit(0)

    elif subcmd in ("install", "--install"):
        from sapas.guard.installer import install, get_startup_dir, STARTUP_SCRIPT_NAME, get_daemon_pid
        vbs_path = get_startup_dir() / STARTUP_SCRIPT_NAME
        daemon_pid = get_daemon_pid()

        # If already installed and daemon is currently running, guide user to 'reinstall' if updating
        if vbs_path.exists() and daemon_pid:
            console.print(Panel(
                Text.assemble(
                    ("Station Guard is already installed and running on this station!\n\n", "bold yellow"),
                    ("  Status     : ", "bold"), (f"Active Daemon running (PID {daemon_pid})\n", "green"),
                    ("  Startup VBS: ", "bold"), (f"{vbs_path}\n\n", "bright_cyan"),
                    ("[Notice]\n", "bold bright_white"),
                    ("If you are upgrading Sapas or wish to refresh the background daemon with new code,\n", "white"),
                    ("please execute the reinstall command instead:\n\n", "white"),
                    ("  sapas guard reinstall\n", "bold bright_green"),
                ),
                title="Station Guard Already Active",
                border_style="yellow"
            ))
            sys.exit(0)

        console.print(Panel(
            Text.assemble(
                ("Sapas Station Guard will install a lightweight auto-start script:\n\n", "bold yellow"),
                ("  Target Path : ", "dim"), (f"{vbs_path}\n\n", "bright_cyan"),
                ("[Security Notice]\n", "bold bright_green"),
                ("  • User-level startup item only — requires NO admin / UAC permissions.\n", "bright_green"),
                ("  • Zero registry, driver, or system file modifications.\n", "bright_green"),
                ("  • Strictly for local workstation safety protection.", "bright_green")
            ),
            title="Station Guard Auto-Start Installation",
            border_style="cyan"
        ))

        # Ask for confirmation unless -y / --yes flag is provided
        if "-y" not in argv and "--yes" not in argv:
            try:
                choice = console.input("[bold yellow]Proceed with installation? [Y/n]: [/]").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"
            if choice not in ("", "y", "yes"):
                console.print("[dim yellow][Cancelled] Installation aborted by user.[/]")
                sys.exit(0)

        ok = install()
        if ok:
            console.print("[bold green][OK] Station Guard successfully configured in Windows Startup![/]")
            is_remote_session = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION"))
            if is_remote_session:
                console.print(Panel(
                    Text.from_markup(
                        "[bold yellow][!] ACTION REQUIRED FOR REMOTE INSTALLATION:[reset]\n\n"
                        "Because this was run via a remote SSH session (Session 0), the physical\n"
                        "screen guard cannot interact with the desktop directly.\n\n"
                        "[bold bright_white]To activate physical desktop protection, reboot the station PC:[reset]\n"
                        "  [bold bright_cyan]shutdown /r /t 0[reset]\n"
                        "[dim](or ask on-site personnel to log into Windows desktop)[/]"
                    ),
                    title="Station Reboot Required",
                    border_style="yellow"
                ))
            else:
                console.print("[bold green][OK] Station Guard daemon started in background.[/]")
        else:
            console.print("[bold red][ERROR] Failed to install Station Guard to Windows Startup.[/]")
        sys.exit(0 if ok else 1)

    elif subcmd in ("reinstall", "--reinstall"):
        from sapas.guard.installer import reinstall, get_startup_dir, STARTUP_SCRIPT_NAME
        vbs_path = get_startup_dir() / STARTUP_SCRIPT_NAME

        console.print(Panel(
            Text.assemble(
                ("Sapas Station Guard will reset all state and reinstall the auto-start script:\n\n", "bold yellow"),
                ("  Target Path : ", "dim"), (f"{vbs_path}\n\n", "bright_cyan"),
                ("[Security Notice]\n", "bold bright_green"),
                ("  • User-level startup item only — requires NO admin / UAC permissions.\n", "bright_green"),
                ("  • Cleans up all previous background processes and state locks.", "bright_green")
            ),
            title="Station Guard Re-installation",
            border_style="cyan"
        ))

        if "-y" not in argv and "--yes" not in argv:
            try:
                choice = console.input("[bold yellow]Proceed with re-installation? [Y/n]: [/]").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"
            if choice not in ("", "y", "yes"):
                console.print("[dim yellow][Cancelled] Re-installation aborted by user.[/]")
                sys.exit(0)

        ok = reinstall()
        if ok:
            console.print("[bold green][OK] Station Guard successfully reinstalled in Windows Startup![/]")
            is_remote_session = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION"))
            if is_remote_session:
                console.print(Panel(
                    Text.from_markup(
                        "[bold yellow][!] ACTION REQUIRED FOR REMOTE RE-INSTALLATION:[reset]\n\n"
                        "Because this was run via a remote SSH session (Session 0), the physical\n"
                        "screen guard cannot interact with the desktop directly.\n\n"
                        "[bold bright_white]To activate physical desktop protection, reboot the station PC:[reset]\n"
                        "  [bold bright_cyan]shutdown /r /t 0[reset]\n"
                        "[dim](or ask on-site personnel to log into Windows desktop)[/]"
                    ),
                    title="Station Reboot Required",
                    border_style="yellow"
                ))
            else:
                console.print("[bold green][OK] Station Guard daemon restarted in background.[/]")
        else:
            console.print("[bold red][ERROR] Failed to reinstall Station Guard.[/]")
        sys.exit(0 if ok else 1)

    elif subcmd in ("uninstall", "--uninstall"):
        from sapas.guard.installer import uninstall
        ok = uninstall()
        if ok:
            console.print("[bold green][OK] Station Guard uninstalled and background process terminated.[/]")
        else:
            console.print("[bold red][ERROR] Failed to uninstall Station Guard.[/]")
        sys.exit(0 if ok else 1)

    else:
        console.print(f"[bold red][Error] Unknown guard command '{subcmd}'.[/]")
        print_guard_help()
        sys.exit(1)


def print_summary_help() -> None:
    help_text = """
[bold cyan]Sapas Station Summary[/] - Interactive Station Yield & Quality Dashboard

[bold]Usage:[/]
  sapas summary \[db_path] \[options]

[bold]Commands & Arguments:[/]
  [bold green]sapas summary[/]                     Auto-detect local SQLite DB in output/ and open HTML dashboard
  [bold green]sapas summary <path/to/file.db>[/]   Generate & open dashboard directly from a specific .db file
  [bold green]--no-open[/]                         Generate HTML dashboard without launching the web browser
  [bold green]help[/]                              Show this help message

[bold]Examples:[/]
  sapas summary
  sapas summary ~/Desktop/sapas_local_FAN_44205100.db
  sapas summary D:/Downloads/yesterday_fixture2.db --no-open
"""
    console.print(help_text.strip())


def _discover_default_db() -> Path | None:
    """Locate the most relevant SQLite database when no path is provided."""
    cwd = Path.cwd()
    candidates: list[Path] = []
    search_dirs = [cwd / "output", cwd]

    # Also check parent workspace output if running inside a project subfolder
    if (cwd.parent / "output").is_dir():
        search_dirs.append(cwd.parent / "output")

    for d in search_dirs:
        if d.is_dir():
            candidates.extend(sorted(d.glob("sapas_local_*.db"), key=lambda p: p.stat().st_mtime, reverse=True))
            if not candidates:
                candidates.extend(sorted(d.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True))
        if candidates:
            break

    return candidates[0] if candidates else None


def handle_summary_cli(argv: list[str]):
    """Handle `sapas summary [db_path]` CLI subcommand."""
    import webbrowser
    from sapas.reports.summary_reporter import generate_summary_dashboard

    if any(arg in ("-h", "--help", "help") for arg in argv):
        print_summary_help()
        sys.exit(0)

    no_open = "--no-open" in argv
    clean_args = [a for a in argv if a not in ("--no-open", "--db")]

    target_db: Path | None = None
    if clean_args:
        raw_path = Path(clean_args[0]).expanduser().resolve()
        if raw_path.is_dir():
            dbs = sorted(raw_path.glob("sapas_local_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not dbs:
                dbs = sorted(raw_path.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not dbs:
                console.print(f"[bold red][Error] No SQLite (.db) files found in directory:[/] {raw_path}")
                sys.exit(1)
            target_db = dbs[0]
        elif raw_path.is_file():
            target_db = raw_path
        else:
            console.print(f"[bold red][Error] Database file not found:[/] {raw_path}")
            sys.exit(1)
    else:
        target_db = _discover_default_db()
        if not target_db:
            console.print(Panel(
                Text.assemble(
                    ("No local SQLite database found in ", "yellow"),
                    ("output/", "bold bright_cyan"),
                    (".\n\n", "yellow"),
                    ("Run at least one test cycle to auto-create ", "white"),
                    ("output/sapas_local_<STATION>_<FIXTURE>.db", "bold cyan"),
                    (",\nor specify a database file path directly:\n  ", "white"),
                    ("sapas summary <path/to/file.db>", "bold green"),
                ),
                title="Station Summary Dashboard",
                border_style="yellow"
            ))
            sys.exit(1)

    try:
        out_html = generate_summary_dashboard(target_db)
    except Exception as exc:
        console.print(f"[bold red][Error] Failed to generate summary dashboard:[/] {exc}")
        sys.exit(1)

    console.print(Panel(
        Text.assemble(
            ("  Database Source : ", "dim"), (f"{target_db}\n", "bright_cyan"),
            ("  HTML Dashboard  : ", "dim"), (f"{out_html}", "bold bright_green"),
        ),
        title="Station Summary Dashboard Generated",
        border_style="green",
    ))

    is_ssh = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION"))
    if not no_open and not is_ssh:
        try:
            webbrowser.open(out_html.resolve().as_uri())
            console.print("[dim]Opened dashboard in your default web browser.[/]")
        except Exception:
            pass


def main():
    first_arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if first_arg == "guard":
        handle_guard_cli(sys.argv[2:])
        return
    elif first_arg == "summary":
        handle_summary_cli(sys.argv[2:])
        return
    elif first_arg in ("lock", "unlock"):
        console.print(f"[yellow][Notice] Unknown command 'sapas {first_arg}'. Did you mean [bold cyan]sapas guard {first_arg}[/]?[/]")
        sys.exit(1)
    elif first_arg:
        import difflib
        matches = difflib.get_close_matches(first_arg, ["guard", "summary"], n=1, cutoff=0.7)
        if matches and not Path(first_arg).exists():
            console.print(f"[bold red][Error] Unknown command '{first_arg}'.[/]")
            console.print(f"[bold yellow]Did you mean:[/] [bold cyan]sapas {matches[0]}[/]?\n")
            sys.exit(1)

    parser = argparse.ArgumentParser(description="Sapas Testing Framework", allow_abbrev=False)
    parser.add_argument("script", nargs="?", help="Path to user test script (.py)")
    parser.add_argument("--tui", action="store_true", help="Start the TUI interface mode.")
    parser.add_argument("--project", help="Specify the project name.")
    parser.add_argument("--station", help="Specify the test station name.")
    parser.add_argument("--test_flow", help="Specify the test flow name.")
    parser.add_argument('--serialNumber', default='sapas999999999', help='Serial number')
    parser.add_argument('--timeStamp', default=datetime.now().strftime('%Y%m%d_%H%M%S'))
    args, remaining_args = parser.parse_known_args()

    # Auto-guard interlock: If remote engineer executes a test without locking, auto-engage Station Guard
    from sapas.guard.lock_manager import ensure_remote_guard_lock, get_override_event
    override_evt = get_override_event()
    if override_evt and (os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION")):
        console.print(Panel(
            Text.assemble(
                ("[!] [DANGER] STATION WAS FORCEFULLY UNLOCKED ON-SITE!\n\n", "bold white on red"),
                ("  Reason : ", "bold yellow"), (f"{override_evt.get('reason')}\n", "white"),
                ("  Time   : ", "bold yellow"), (f"{override_evt.get('time')}\n\n", "dim"),
                ("  Safety Interlock Engaged:\n", "bold red"),
                ("  Personnel may be present near the fixture or handling the DUT.\n", "yellow"),
                ("  To resume remote execution safely, inspect physical station and run: 'sapas guard lock'\n", "bright_cyan"),
            ),
            title="⚠️ EMERGENCY SAFETY BRAKE ⚠️",
            border_style="red"
        ))
        sys.exit(1)

    auto_locked = ensure_remote_guard_lock()
    if auto_locked:
        console.print("[bold yellow][!] [AUTO-GUARD] Remote execution detected without active lock![/]")
        console.print(f"[bold yellow]    Engaging Station Guard on station desktop for human safety... (Source: {auto_locked['ip']})[/]\n")

    context = setup_context(args)

    project_name = context.get("PROJECT_NAME", "Unknown")
    station_name = context.get("STATION_NAME", "Unknown")
    final_flow = args.test_flow or context.env.get("TEST_FLOW") or f"{station_name}.flow"

    # Verify flow file existence before proceeding (unless running a standalone script)
    if not (args.script and args.script.endswith(".py")):
        workspace_root = Path(context.get("WORKSPACE_ROOT", Path.cwd()))
        flow_dir = workspace_root / project_name / "flows"
        flow_path = flow_dir / final_flow
        if not flow_path.exists():
            matches = [path for path in flow_dir.glob("*.flow") if path.name.lower() == final_flow.lower()]
            if matches:
                final_flow = matches[0].name
            else:
                print(f"\033[91m[Error] Flow file '{final_flow}' not found in project '{project_name}' flows folder!\033[0m")
                print(f"Expected path: {flow_path}")
                sys.exit(1)

    if args.script and args.script.endswith(".py"):
        # Mode A: execute a standalone script.
        script_path = Path(args.script).resolve()
        from sapas.core.user_runner import run_user_script
        run_user_script(script_path.name, cli_args=args, user_args=remaining_args)
    elif args.tui:
        # Mode B: wrap it with a TUI shell.
        from sapas.tui.app import SapasDashboard
        
        # Pass the existing context and args into the TUI,
        # so it doesn't have to initialize them blindly on its own.
        app = SapasDashboard(context=context, cli_args=args)
        app.run()
        sys.exit(0)
    else:
        draw_welcome_screen(project_name, station_name, final_flow)
        try:
            while True:
                # Determine Shopfloor status tag using Text object to prevent leakage
                is_sf_enabled = context.get("ENABLE_SHOPFLOOR", False)
                prompt_text = Text()
                
                if is_sf_enabled:
                    prompt_text.append(" SHOPFLOOR:ON ", style="bold white on green")
                else:
                    prompt_text.append(" SHOPFLOOR:OFF ", style="blink bold red on white reverse")
                
                # Add a normal space and the rest of the prompt in standard white
                prompt_text.append(" ")
                prompt_text.append("Scan/Enter Serial Number", style="bold white")
                # Lightskyblue color from the logo: (135, 206, 250)
                prompt_text.append(" (or type 'exit'): ", style="rgb(135,206,250)")
                
                sn_input = console.input(prompt_text).strip()
                if sn_input.lower() in ['exit', 'quit', 'q']:
                    console.print("[dim]Goodbye![/]")
                    break
                
                if sn_input:
                    context = setup_context(args) 
                    runner = Runner(context)
                    
                    args.serialNumber = sn_input
                    args.timeStamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                    runner.execute_flows(args)

                    final_status = context.get('ERROR_CODE')
                    
                    if final_status == "PASS":
                        status_style = "bold green"
                        border_style = "green"
                        display_text = f"✅ [bold green][blink]SERIAL NUMBER: {args.serialNumber} \n\nFINAL RESULT: {final_status} - TEST SUCCESS[/]"
                    elif final_status == "CHECK":
                        status_style = "bold yellow"
                        border_style = "yellow"
                        display_text = f"⚠️ [bold yellow][blink]SERIAL NUMBER: {args.serialNumber} \n\nFINAL RESULT: {final_status} - MANUAL CHECK REQUIRED[/]"
                    else:
                        status_style = "bold red"
                        border_style = "red"
                        display_text = f"❌ [bold red][blink]SERIAL NUMBER: {args.serialNumber} \n\nFINAL RESULT: {final_status} - TEST FAILED[/]"

                    result_panel = Panel(
                        Align.center(display_text, vertical="middle"),
                        border_style=border_style,
                        expand=True,
                        padding=(1, 2)
                    )

                    console.print("\n")
                    console.print(result_panel)
                    console.print("\n")

        except KeyboardInterrupt:
            console.print("\n[yellow]User interrupted the station loop.[/]")

if __name__ == '__main__':
    main()