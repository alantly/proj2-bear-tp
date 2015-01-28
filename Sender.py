import sys
import getopt

import Checksum
import BasicSender

'''
This is a skeleton sender class. Create a fantastic transport protocol here.
'''
class Sender(BasicSender.BasicSender):
    # stdin TA said might not be in the test at all
    # when working with SACK, pay attention to both cum_ack and specific ack
    # -> out of range error ??
    # use attribute or Sender to check if it's in SACK mode or not from an ACK (on top of enableing the option)

    MAX_DATA_SIZE = 1472
    WINDOW_SIZE = 5
    TIMEOUT = 0.5

    def __init__(self, dest, port, filename, debug=False, sackMode=False):
        super(Sender, self).__init__(dest, port, filename, debug)
        self.window = []
        self.dup_ack = None
        if sackMode:
            raise NotImplementedError #remove this line when you implement SACK

    def get_message_type(self, seqno, next_msg):
        msg_type = 'data'
        if seqno == 0:
            msg_type = 'start'
        elif next_msg == "":
            msg_type = 'end'
        return msg_type

    # according to the spec:
    # this leaves 1472 bytes for your entire packet (message type, sequence number, data, and checksum)
    # yet I tried it and then the size of data packet is under 1500, but still a little off
    def calculate_data_size(self, seqno):
        return Sender.MAX_DATA_SIZE - sys.getsizeof(seqno) - sys.getsizeof('start') - sys.getsizeof(Checksum.generate_checksum('0xffffffff'))

    def packets_in_flight(self):
        return [elem[0] for elem in self.window]

    def get_ack_seq(self, ack):
        return self.split_packet(ack)[1]

    def is_seq_in_flight(self, ack_seq):
        return ack_seq in [self.split_packet(x)[1] for x in self.packets_in_flight()]

    def get_first_elem_ack(self):
        first_packet = self.get_first_packet_in_flight()
        return self.get_ack_seq(first_packet)

    def get_first_packet_in_flight(self):
        return self.window[0][0]

    def get_dup_count(self):
        return self.dup_ack[1]

    def get_dup_seq(self):
        return self.dup_ack[0]

    def read_next_msg(self,seqno):
        data_size = self.calculate_data_size(seqno + 1)
        next_msg = self.infile.read(data_size)
        msg_type = self.get_message_type(seqno, next_msg)
        return msg_type,next_msg

    def populate_window_and_send(self,msg_type,msg,data_size,seqno):
        while len(self.window) < self.WINDOW_SIZE and msg_type != 'end':
            msg_type, next_msg = self.read_next_msg(seqno)
            packet = self.make_packet(msg_type, seqno, msg)
            self.send(packet)
            self.window.append((packet, False))
            msg = next_msg
            seqno += 1
        return seqno, msg_type, msg

    # Main sending loop.
    def start(self):
        if not sackMode:
            seqno = 0
            data_size = self.calculate_data_size(seqno)

            msg = self.infile.read(data_size)
            msg_type = None

            seqno, msg_type, msg = self.populate_window_and_send(msg_type,msg,data_size,seqno)

            while len(self.window) > 0:
                response = self.receive(self.TIMEOUT)
                self.handle_response(response)
                if msg_type != 'end':
                    self.populate_window_and_send(msg_type,msg,data_size,seqno)
            self.infile.close()
        else:
            print ("Implement SACKMODE here")
    def handle_response(self, response):
        if response:
            if not self.dup_ack or self.get_dup_seq() != self.get_ack_seq(response):
                self.dup_ack = (self.get_ack_seq(response), 1)
                self.handle_new_ack(response)
            else:
                self.dup_ack = (self.get_ack_seq(response), self.dup_ack[1] + 1)
                self.handle_dup_ack(response)
        else:
            # send everything in the window if it's a timeout
            self.handle_timeout()

    def handle_timeout(self):
        for packet in self.packets_in_flight():
                self.send(packet)

    def handle_new_ack(self, ack):
        msg_type = self.split_packet(ack)[0]
        if Checksum.validate_checksum(ack) and msg_type == 'ack':
            ack_seq = self.get_ack_seq(ack)
            # for easier computation
            ack_seq = str(int(ack_seq) - 1)
            if self.is_seq_in_flight(ack_seq):
                while len(self.window) > 0 and int(self.get_first_elem_ack()) <= int(ack_seq):
                    self.window.pop(0)

    # fast retransmission only occurs at the fourth packet
    # only timeout will retransmit the packets after this point
    def handle_dup_ack(self, ack):
        if self.get_dup_count() == 4:
            self.send(self.get_first_packet_in_flight)

    def log(self, msg):
        if self.debug:
            print msg


'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print "BEARS-TP Sender"
        print "-f FILE | --file=FILE The file to transfer; if empty reads from STDIN"
        print "-p PORT | --port=PORT The destination port, defaults to 33122"
        print "-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost"
        print "-d | --debug Print debug messages"
        print "-h | --help Print this usage message"
        print "-k | --sack Enable selective acknowledgement mode"

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                               "f:p:a:dk", ["file=", "port=", "address=", "debug=", "sack="])
    except:
        usage()
        exit()

    port = 33122
    dest = "localhost"
    filename = None
    debug = False
    sackMode = False

    for o,a in opts:
        if o in ("-f", "--file="):
            filename = a
        elif o in ("-p", "--port="):
            port = int(a)
        elif o in ("-a", "--address="):
            dest = a
        elif o in ("-d", "--debug="):
            debug = True
        elif o in ("-k", "--sack="):
            sackMode = True

    s = Sender(dest, port, filename, debug, sackMode)
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
