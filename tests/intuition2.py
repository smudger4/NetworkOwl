# listener client for Intuition-pv / Network Owl
# prints XML responses received over multicast
# changed to use Twisted framework
#
# v0.3 Nick Smith 11 November 2012


from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
import struct
import sys
import xml.etree.ElementTree as ET


INDIGO = False

multicast_group = '224.192.32.19'
multicast_port = 22600



class NetworkOwl(DatagramProtocol):

    def startProtocol(self):
        """
        Called after protocol has started listening.
        """
        # Join multicast group:
        self.transport.joinGroup(multicast_group)
        
    def datagramReceived(self, datagram, address):
        print "Datagram %s received from %s" % (repr(datagram), repr(address))
        # Rather than replying to the group multicast address, we send the
        # reply directly (unicast) to the originating port:
        self.transport.write("ack", address)
        
        # Create an Element Tree instance from the data received from the Network Owl
        root = ET.fromstring(datagram)
        
        if INDIGO == True:
            indigo.server.log("Intuition: " + root.tag + " packet received")
        else:
            print root.tag
        
        # Solar data packet
        if root.tag == 'solar':
            for solar in root.findall('current'):
                gen_watts = solar.find('generating').text
                exp_watts = solar.find('exporting').text
                
                # remove the decimal points
                if gen_watts.endswith('.00'):
                    gen_watts = gen_watts[:-3]
                if exp_watts.endswith('.00'):
                    exp_watts = exp_watts[:-3]
                
                if INDIGO == True:
                    indigo.variable.updateValue("Intuition_Gen", gen_watts)
                    indigo.variable.updateValue("Intuition_Exp", exp_watts)
                    indigo.server.log("Intuition: generated watts: " + gen_watts)
                    indigo.server.log("Intuition: exported watts: " + exp_watts)
                else:
                    print "Gen: %s  Exp: %s" % (gen_watts, exp_watts)
        
        # Electricity data packet - repeats the data for each of the 3 channels supported by the transmitter
        # Used power is channel 0
        if root.tag == 'electricity':
            for elem in root.findall('chan'):
                if elem.get('id') == '0':
                    used_watts = elem.find('curr').text
                    
                    # remove the decimal points
                    if used_watts.endswith('.00'):
                        used_watts = used_watts[:-3]
                
                    if INDIGO == True:
                        indigo.variable.updateValue("Intuition_Used", used_watts)
                        indigo.server.log("Intuition: used watts: " + used_watts)
                    else:
                        print "Used: %s" % used_watts
                    
        # also weather packet that can be received
        
reactor.listenMulticast(multicast_port, NetworkOwl())
reactor.run()