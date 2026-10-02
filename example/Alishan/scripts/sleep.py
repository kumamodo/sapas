import sapas

from sapas import ActionItem


@sapas.param("--sec", type=int, required=True, help="Seconds to sleep")

class Sleep(ActionItem):
    """
    [Example] A simple sleep action using custom parameters.
    Usage: sapas sleep.py --sec 5
    """
    def run_action(self):
        sec = int(sapas.args.sec)
        sapas.sleep(sec)

