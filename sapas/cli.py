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

def setup_context(args):
    # [Environment Initialization] Responsible for converting all YAML files
    #  into a unified context and wiring it into the global rt.

    # Load the base environment configuration (site_infra.yaml).
    env_path = Path("site_infra.yaml")
    env = load_yaml(env_path) if env_path.exists() else {}

    # Determine the project and test station
    # priority: CLI arguments > site_infra.yaml.
    project_name = args.project or env.get("PROJECT_NAME")
    station_name = args.station or env.get("STATION_NAME")

    if not project_name or not station_name:
        print("\033[91m[Error] Project or Station not specified!\033[0m")
        sys.exit(1)

    workspace_root = Path.cwd()
    project_dir = workspace_root / project_name

    # Define the path and check whether it exists.
    station_path = project_dir / "stations" / f"{station_name}" / "station.yaml"
    project_config_path = project_dir / "configs" / "project.yaml"

    if not station_path.exists():
        print(f"\033[91m[Error] Station config not found: {station_path}\033[0m")
        sys.exit(1)

    station_var = load_yaml(station_path)
    project_var = load_yaml(project_config_path) if project_config_path.exists() else {}

    # Create a single unified Context and connect it to the global rt registry/bus.
    context = ExecutionContext(station_var, project_var, env_cfg=env)
    context.set('WORKSPACE_ROOT', str(workspace_root))
    context.set('PROJECT_NAME', project_name)
    context.set('STATION_NAME', station_name)

    # Initialize the global runtime.
    rt.init(context)
    return context

def main():
    parser = argparse.ArgumentParser(description="Sapas Testing Framework", allow_abbrev=False)
    parser.add_argument("script", nargs="?", help="Path to user test script (.py)")
    parser.add_argument("--tui", action="store_true", help="Start the TUI interface mode.")
    parser.add_argument("--project", help="Specify the project name.")
    parser.add_argument("--station", help="Specify the test station name.")
    parser.add_argument("--test_flow", help="Specify the test flow name.")
    parser.add_argument('--serialNumber', default='sapas999999999', help='Serial number')
    parser.add_argument('--timeStamp', default=datetime.now().strftime('%Y%m%d_%H%M%S'))
    args, remaining_args = parser.parse_known_args()

    context = setup_context(args)

    project_name = context.get("PROJECT_NAME", "Unknown")
    station_name = context.get("STATION_NAME", "Unknown")
    final_flow = args.test_flow if args.test_flow else f"{station_name}.flow"

    if args.script and args.script.endswith(".py"):
        # Mode A: execute a standalone script.
        script_path = Path(args.script).resolve()
        from sapas.core.user_runner import run_user_script
        run_user_script(script_path.name, cli_args=args, user_args=remaining_args)
    elif args.tui:
        # Mode B: wrap it with a TUI shell.
        from sapas.tui.sapas_tui_dashboard import SapasDashboard
        
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