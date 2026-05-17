
import time

from sapas import ActionItem


class Sleep(ActionItem):
    @classmethod
    def build_parser(cls, parser):
        parser.add_argument("--sec", type=int, required=True)

    def run_action(self):
        sec = int(self.args.sec)
        self.log('Set {} sec to sleep'.format(sec))
        while sec:
            self.log('Countdown {} sec'.format(sec))
            time.sleep(1)
            sec -= 1
