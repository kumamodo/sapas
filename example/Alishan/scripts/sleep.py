
import time
import sapas

from sapas import ActionItem


@sapas.arg("--sec", type=int, required=True, help="Seconds to sleep")

class Sleep(ActionItem):
    """
    [Example] A simple sleep action using custom arguments.
    Usage: sapas sleep.py --sec 5
    """
    def run_action(self):
        sec = int(self.args.sec)
        self.log('Set {} sec to sleep'.format(sec))
        while sec:
            self.log('Countdown {} sec'.format(sec))
            time.sleep(1)
            sec -= 1
