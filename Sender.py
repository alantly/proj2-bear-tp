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

    MAX_DATA_SIZE = 500#1472
    WINDOW_SIZE = 5
    TIMEOUT = 0.5

    def __init__(self, dest, port, filename, debug=False, sackMode=False):
        super(Sender, self).__init__(dest, port, filename, debug)
        self.window = []
        self.dup_ack = None
        self.delay = 0

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

    def sa_packets_in_flight(self):
        return [elem[0] for elem in self.window if elem[1] == False]

    def get_ack_seq(self, ack):
        if sackMode:
            return self.get_cumul_ack(ack)
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

    def get_cumul_ack(self,ack):
        return self.split_packet(ack)[1].split(';')[0]

    def get_sel_ack(self,ack):
        return self.split_packet(ack)[1].split(';')[1].split(',')

    # Main sending loop.
    def start(self):
        seqno = 0
        data_size = self.calculate_data_size(seqno)

        msg = self.infile.read(data_size)
        msg_type = None

        # populating the window
        while seqno < self.WINDOW_SIZE and msg_type != 'end':
            data_size = self.calculate_data_size(seqno + 1)
            next_msg = self.infile.read(data_size)
            msg_type = self.get_message_type(seqno, next_msg)
            packet = self.make_packet(msg_type, seqno, msg)
            self.send(packet)
            # (packet, is_acked) note that is_acked is a boolean indicating whether this packet has been acked
            self.window.append([packet, False])
            msg = next_msg
            seqno += 1


        while len(self.window) > 0:
            response = self.receive(self.TIMEOUT)
            if response:
                self.delay = 0
            else:
                self.delay += self.TIMEOUT
            if self.delay >= 10:
                break

            self.handle_response(response)
            if msg_type != 'end':
                while msg_type != 'end' and len(self.window) < self.WINDOW_SIZE:
                    data_size = self.calculate_data_size(seqno + 1)
                    next_msg = self.infile.read(data_size)
                    msg_type = self.get_message_type(seqno, next_msg)
                    packet = self.make_packet(msg_type, seqno, msg)
                    self.send(packet)
                    self.window.append([packet, False])
                    msg = next_msg
                    seqno += 1
        self.infile.close()

    def handle_response(self, response):
        if response:
            if not Checksum.validate_checksum(response):
                return
            ack_seq = self.get_ack_seq(response)
            if not self.dup_ack or self.get_dup_seq() != ack_seq:
                self.dup_ack = (ack_seq, 1)
                self.SA_handle_response(response)
                self.handle_new_ack(response)
            else:
                self.dup_ack = (ack_seq, self.dup_ack[1] + 1)
                self.SA_handle_response(response)
                self.handle_dup_ack(response)
        else:
            # send everything in the window if it's a timeout
            self.log("Timeout")
            self.dup_ack = None
            self.handle_timeout()

    def SA_handle_response(self,response):
        if sackMode:
            cumul_ack = self.get_cumul_ack(response)
            sel_ack = self.get_sel_ack(response)
            sel_ack.append(str(int(cumul_ack) - 1))
            for elem in self.window:
                if self.get_ack_seq(self.get_pkt_from_wind_elem(elem)) in sel_ack:
                    self.set_sa_found(elem)
            #self.print_win_ack()

    def print_win_ack(self):
        print([(self.get_cumul_ack(elem[0]),elem[1]) for elem in self.window])

    def set_sa_found(self,elem):
        if not elem[1]:
            elem[1] = True

    def get_pkt_from_wind_elem(self,elem):
        return elem[0]

    def handle_timeout(self):
        for packet in self.sa_packets_in_flight():
            self.send(packet)

    def handle_new_ack(self, ack):
        msg_type = self.split_packet(ack)[0]
        if (msg_type == 'ack' or msg_type == 'sack'):
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
            self.log("Dup_ack")
            if sackMode:
                self.handle_timeout()
            else:
                self.send(self.get_first_packet_in_flight())

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
