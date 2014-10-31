import random

from BasicTest import *

class SmallFileTest(BasicTest):
    def handle_packet(self):
        for p in self.forwarder.in_queue:
            self.forwarder.out_queue.append(p)

        # empty out the in_queue
        self.forwarder.in_queue = []
