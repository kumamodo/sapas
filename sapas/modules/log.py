from sapas.runtime.runtime import ctx
from rich.console import Console

# Create a "color-blind" console to convert
# Rich objects into plain text with proper alignment.
_plain_console = Console(width=200, color_system=None, force_terminal=False)

_log_deprecated_shown = False

def _log(tag, *args):
    # Smart Detection: Priority 1: Current active item logger, Priority 2: Global runner logger
    logger = None
    active_item = None
    try:
        logger = ctx.get("ACTIVE_LOGGER") or ctx.get("RUNNER_LOGGER")
        active_item = ctx.get("ACTIVE_ITEM")
    except RuntimeError:
        pass

    # If the user called info/warn/error without a specific tag (i.e., tag is 'INFO'/'WARN'/'ERROR'),
    # we try to resolve it to ACTION or USER if we are inside a script.
    if tag == 'INFO':
        if active_item:
            from sapas.core.test_item import TestItem
            from sapas.core.action_item import ActionItem
            if isinstance(active_item, TestItem):
                tag = 'USER'
            elif isinstance(active_item, ActionItem):
                tag = 'ACTION'

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

def log(tag, *args):
    global _log_deprecated_shown
    if not _log_deprecated_shown:
        _log('WARN', "[DEPRECATION] sapas.log() is deprecated and will be removed in future versions.")
        _log('WARN', "             Please use sapas.info(), sapas.warn(), or sapas.error() instead.")
        _log_deprecated_shown = True
    _log(tag, *args)

def info(msg, *args, tag='INFO'):
    _log(tag, msg, *args)

def warn(msg, *args, tag='WARN'):
    _log(tag, msg, *args)

def error(msg, *args, tag='ERROR'):
    _log(tag, msg, *args)

def log_banner(title):
    line_width = 60
    separator = "=" * line_width

    inner_content = f"={title.center(line_width - 2)}="
    
    _log('ITEM', separator)
    _log('ITEM', inner_content)
    _log('ITEM', separator)