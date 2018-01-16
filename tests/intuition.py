# listener client for Intuition-pv / Network Owl
# prints XML responses received over multicast
#
# v0.2 Nick 10 October 2012


import socket
import struct
import sys
import xml.etree.ElementTree as ET


INDIGO = True

multicast_group = '224.192.32.19'
server_address = ('', 22600)

try:
	# Create the socket
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

	# Bind to the server address
	sock.bind(server_address)

	# Tell the operating system to add the socket to the multicast group
	# on all interfaces.
	group = socket.inet_aton(multicast_group)
	mreq = struct.pack('4sL', group, socket.INADDR_ANY)
	sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

except socket.error, msg:
	if INDIGO == True:
		indigo.server.log("Intuition: socket error, closing")
	else:
		print >>sys.stderr, 'Intuition: socket error, closing'
	sock.close()
	sys.exit(1)

# Receive/respond loop
while True:
    if INDIGO == True:
        indigo.server.log("Intuition: waiting to receive message")
    else:
        print >>sys.stderr, '\nwaiting to receive message'

    data, address = sock.recvfrom(1024)
    num_bytes = len(data)

    if INDIGO == False:
        print >>sys.stderr, 'received %s bytes from %s' % (num_bytes, address)
        print >>sys.stderr, data
        print >>sys.stderr, 'sending acknowledgement to', address
    #else:
        #indigo.server.log("Intuition: received " + str(num_bytes) + " bytes from " + str(address))
        #indigo.server.log(str(data))
        #indigo.server.log("Intuition: sending acknowledgement to " + str(address))
       
    sock.sendto('ack', address)

    # Create an Element Tree instance from the data received from the Network Owl
    root = ET.fromstring(data)
    
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
                print gen_watts, exp_watts
    
    # Electricity data packet - repeats the data for each of the 3 channels supported by the transmitter
    # Used power is channel 0
    if root.tag == 'electricity':
        #for elem in root.findall(".//curr/..[@id='0']"):
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
                    print used_watts
                
    # also weather packet that can be received
    	
    




