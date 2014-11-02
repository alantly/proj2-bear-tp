import random

from BasicTest import *

"""
This tests random packet drops. We randomly decide to drop about half of the
packets that go through the forwarder in either direction.

Note that to implement this we just needed to override the handle_packet()
method -- this gives you an example of how to extend the basic test case to
create your own.
"""
class DupDropTest(BasicTest):
	i = 0
	def handle_packet(self):
		pass
		#for p in self.forwarder.in_queue:
			#if str(p).split('|')[0] == 'ack' and str(p).split('|')[1] == '1' and self.i == 0:
			#	p.update_packet('shitz', p.seqno, p.data, None)
			#self.forwarder.out_queue.append(p)
		# empty out the in_queue
		#self.forwarder.in_queue = []

	def split_packet(self, message):
		pieces = message.split('|')
		msg_type, seqno = pieces[0:2] # first two elements always treated as msg type and seqno
		checksum = pieces[-1] # last is always treated as checksum
		data = '|'.join(pieces[2:-1]) # everything in between is considered data
		return msg_type, seqno, data, checksum
