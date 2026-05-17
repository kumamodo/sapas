from sapas.runtime.runtime import ctx
from rich.console import Console

# Create a "color-blind" console to convert
# Rich objects into plain text with proper alignment.
_plain_console = Console(width=200, color_system=None, force_terminal=False)

def log(tag, *args):
    logger = ctx.get("RUNNER_LOGGER")

    formatted_tag = f"[{tag:^8}]"
    
    for arg in args:
        # If it is a Rich object such as a Table or Panel.
        if hasattr(arg, "__rich__") or hasattr(arg, "__rich_console__"):
            # Convert the object into a plain text block.
            with _plain_console.capture() as capture:
                _plain_console.print(arg)
            
            # Split the text block into a list of lines.
            lines = capture.get().splitlines()
            for line in lines:
                # Skip completely empty lines, but preserve the table border lines.
                if not line.strip() and not line:
                    continue
                
                full_msg = f"{formatted_tag} {line}"
                if logger:
                    # Call info() for each line individually.
                    # This way, the log file will look like:
                    # [timestamp] - INFO - +-------+
                    logger.info(full_msg)
                else:
                    print(f"INFO - {full_msg}")
        else:
            full_msg = f"{formatted_tag} {arg}"
            # Plain text message.
            if logger:
                logger.info(full_msg)
            else:
                print(full_msg)

def log_banner(title):
    line_width = 60
    separator = "=" * line_width

    inner_content = f"={title.center(line_width - 2)}="
    
    log('ITEM', separator)
    log('ITEM', inner_content)
    log('ITEM', separator)