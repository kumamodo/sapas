import sapas
from sapas import ActionItem

class DemoLogs(ActionItem):
    """
    [Example] Demonstrates the use of sapas.info, sapas.warn, and sapas.error.
    The tags will automatically appear as [  USER  ] because this is a user-written ActionItem.
    """
    def run_action(self):
        # 1. Standard informational log (Automatically tagged as [  USER  ])
        sapas.info("This is an informational message using sapas.info()")
        
        # 2. Warning message (Tagged as [  WARN  ])
        sapas.warn("This is a warning message using sapas.warn()")
        
        # 3. Error message (Tagged as [ ERROR  ])
        # Note: In ActionItem, sapas.error() or self.error() will be logged but 
        # won't stop execution unless you raise an exception.
        sapas.error("This is an error message using sapas.error()")
        
        sapas.info("Demo completed. Check the colors in TUI!")
