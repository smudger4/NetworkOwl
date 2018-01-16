#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Interface to NetworkOwl device
# Reads solar PV generation, electricity usage, weather, heating & hot water data & updates device states
# Reads 3 phases if device type is Intution-lc
# V1.6  16 January 2018
# https://smudger4.github.io
#
#
# v1.6: repackaged for Indigo Plugin Library - no functional changes
# v1.5: updated electricity sections to handle new V2 XML specification alongside existing
# v1.4: updated hot water & heating sections to support updated firmware (2.6)
# v1.3: rewritten to replace references to Twisted with more generic networking code, as Twisted no longer supported by Indigo when running on OS X 10.9 (Mavericks) because Twisted libraries were removed from the old version of OS X Python that Indigo relies on.
# v1.2: adds read-only support for hot water & heating controls
# v1.1: extends electricity packet to support 3-phase
# v1.0: initial version


import os
import sys
import struct
import time
import socket

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


########################################
########################################


class NetworkOwl():
    """Class to interface with the NetworkOWL electricity monitor device.
    
    Reads the multicast stream sent by the NetworkOwl & creates packets to represent
    each kind of datagram. Supported types are Solar, Electricity, Weather, Hot water & 
    Heating. 
    Calls associatePacket to update the object represented by the plugin instance
    variable. In the case of Indigo, this will be the Plugin instance, but for other uses
    adapt the associatePacket method to interface to the surrounding framework.
    
   Instance variables:
        plugin  - represents the object containing an instance of this class.
        
    Constants:
        MULTICAST_GROUP - defined by NetworkOwl hardware: group IP address.
        MULTICAST_PORT  - defined by NetworkOwl hardware: port number.
     
    """   
    # constants for NetworkOwl
    MULTICAST_GROUP = '224.192.32.19'
    MULTICAST_PORT = 22600

    ########################################    
    def __init__(self, plugin):
        """Store the reference to the containing object."""
        self.plugin = plugin

    ########################################
    def startProtocol(self):
        """Joins the multicast group."""
        self.plugin.mylogger.log(4, "Intuition: startProtocol called")
        sock = None
        
        try:
            # Create the socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

            # Bind to the server address
            sock.bind(('', NetworkOwl.MULTICAST_PORT))

            # Tell the operating system to add the socket to the multicast group
            # on all interfaces.
            group = socket.inet_aton(NetworkOwl.MULTICAST_GROUP)
            mreq = struct.pack('4sL', group, socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        except socket.error, msg:
            self.mylogger.logError("Intuition: socket error, closing")
            sock.close()
        
        return sock

    ########################################
    def runProtocol(self, sock):      
        """
            wait loop for retrieving multicast packets from socket.
            assumes is being run in a separate thread so is OK to block waiting
            sends ACK back to sending station
            then processes the received packet
            loop until the main Indigo plugin thread variable is reset
        """
        while self.plugin.stopThread == False:
        
            # check config hasn't changed
            self.plugin.checkConfig()
            
            self.plugin.mylogger.log(4, "Intuition: waiting to receive message")

            data, address = sock.recvfrom(1024)
            num_bytes = len(data)

            self.plugin.mylogger.log(4, 'received %s bytes from %s' % (num_bytes, address))
            self.plugin.mylogger.log(4, data)
            self.plugin.mylogger.log(4, 'sending acknowledgement to %s' % repr(address))

            # Rather than replying to the group multicast address, we send the
            # reply directly (unicast) to the originating port:
            sock.sendto('ack', address)

            # process the data just received from the Network Owl
            self.processDataPacket(data)
            
            self.plugin.sleep(1)
        
    ########################################
    def processDataPacket(self, datagram):
        """Parse the datagram & create appropriate data packet instance."""
    
        #Create an Element Tree instance to hold the data received from the Network Owl
        root = ET.fromstring(datagram)
        dev = None
                
        self.plugin.mylogger.log(3, "NetworkOwl: " + root.tag + " packet received")
        
        packet = None
        
        # get device associated with the MAC address of packet received
        packetAddress = root.get('id')
        self.plugin.mylogger.log(4, "NetworkOwl: packet address: %s" % packetAddress)
        
        # check if we recognise the MAC address, if not ignore the datagram
        if packetAddress not in self.plugin.deviceDict:
            self.mylogger.logError("Received packet from unknown NetworkOwl %s: create NetworkOwl device in Indigo" % packetAddress)
        else:            
            # Solar data packet
            if root.tag == 'solar':
                packet = SolarPacket(self.plugin, packetAddress, root)
                if packet.isValid():
                    packet.associate()
                       
            # Electricity data packet 
            elif root.tag == 'electricity':
                packet = ElectricityPacket(self.plugin, packetAddress, root)
                if packet.isValid():
                    packet.associate()
                
            # weather data packet
            elif root.tag == 'weather':
                packet = WeatherPacket(self.plugin, packetAddress, root)
                if packet.isValid():
                    packet.associate()
                
            # heating data packet
            elif root.tag == 'heating':
                packet = HeatingPacket(self.plugin, packetAddress, root)
                if packet.isValid():
                    packet.associate()
                                        
            # hot water data packet
            elif root.tag == 'hot_water':
                packet = HotWaterPacket(self.plugin, packetAddress, root)
                if packet.isValid():
                    packet.associate()
                             
            # if we've received a packet we know how to deal with, 
            # we've processed it by now  
            if packet == None:
                # having created a packet from the multicast stream, 
                # now associate the packet with the server
                #dev = self.plugin.deviceDict[packetAddress]
                #self.associatePacket(packet, dev)
            #else:
                # no idea what to do with this type of packet, just log an error
                self.mylogger.logError("Unknown '%s' packet received" % root.tag)
        
    ########################################
    def stripDecimals(self, inParam):
        """Remove '.00' from the end of value passed in"""
        outParam = inParam
        if inParam.endswith('.00'):
            outParam = inParam[:-3]
        return outParam
        
        

########################################
########################################


class NetworkOwlPacket(object):
    """Base class for all NetworkOwl data packets.
    
    Instance variables:
        reading_time    - time packet was read
        mac_address     - MAC address of packet
        packet_type     - type of packet as a single word
        plugin          - reference to the containing plugin context
        device          - reference to the device once associated
        owlType         - kind of Owl device that sent the packet
        valid           - is the packet a valid one?
            
    """
    ########################################
    def __init__(self, plugin, addr):
        """Record time & MAC address."""
        self.reading_time = time.strftime('%Y/%m/%d %H:%M:%S')
        self.mac_address = addr
        self.packet_type = ""
        self.xml_version = None
        self.plugin = plugin
        self.device = plugin.deviceDict[addr]
        self.owlType = str(self.device.states["networkOwlType"])
        self.valid = False

        
    ########################################
    def stripDecimals(self, inParam):
        """Remove '.00' from the end of value passed in"""
        outParam = inParam
        if inParam.endswith('.00'):
            outParam = inParam[:-3]
        return outParam

    ########################################        
    def isValid(self):
        return self.valid
        
    ########################################        
    def associate(self):
        """Associate the packet with Indigo"""
        self.device.updateStateOnServer("lastUpdated", self.reading_time)
        
    ########################################
    
    def splunk(self, field, value):
        """Log packet data in a Splunk-friendly format"""
        self.plugin.mylogger.log(2, "NetworkOwl: %s=%s" % (field, value))



########################################
########################################

class SolarPacket(NetworkOwlPacket):
    """NetworkOwl solar packet.
    
    Instance variables:
        gen_watts       - watts being generated now.
        exp_watts       - watts being exported now..
        gen_watts_today - total number of watts generated today.
        exp_watts_today - total number of watts exported today.
        
        <solar id='xxxx'>
            <current>
                <generating units='w'>84.00</generating>
                <exporting units='w'>84.00</exporting>
            </current>
            <day>
                <generated units='wh'>145.56</generated>
                <exported units='wh'>145.56</exported>
            </day>
        </solar>
        
    
    """
    ########################################
    def __init__(self, plugin, addr, root):
        """Initialise solar instance variables."""
        NetworkOwlPacket.__init__(self, plugin, addr)
        self.packet_type = "solar"
        self.gen_watts = 0
        self.exp_watts = 0
        self.gen_watts_today = 0
        self.exp_watts_today = 0
        
        # work out which version of XML we're dealing with & behave accordingly
        self.xml_version = root.get('ver')
         
        if self.xml_version == None:
            # original version of the packet with no version number
            # extract & process current readings
            self.valid = True
            currSolar = root.find('current')
            gen_watts = currSolar.find('generating').text
            exp_watts = currSolar.find('exporting').text
         
            # remove the decimal points
            self.gen_watts = self.stripDecimals(gen_watts)
            self.exp_watts = self.stripDecimals(exp_watts)
            
            # extract & process whole day readings
            daySolar = root.find('day')
            self.gen_watts_today = daySolar.find('generated').text
            self.exp_watts_today = daySolar.find('exported').text
            
        else:
            # unknown XML format - log error
            self.plugin.mylogger.logError(u"unrecognised solar packet received")


    ########################################
    def associate(self):
        """Update Indigo with solar packet data"""
        NetworkOwlPacket.associate(self)
        
        self.device.updateStateOnServer("genWattsNow", self.gen_watts)
        self.device.updateStateOnServer("expWattsNow", self.exp_watts)
        self.device.updateStateOnServer("genWattsToday", self.gen_watts_today)
        self.device.updateStateOnServer("expWattsToday", self.exp_watts_today)
        
        self.plugin.mylogger.log(3, "NetworkOwl: generating watts: " + self.gen_watts)
        self.plugin.mylogger.log(3, "NetworkOwl: exporting watts: " + self.exp_watts)
        
        NetworkOwlPacket.splunk(self, "solar_gen_watts", self.gen_watts)
        NetworkOwlPacket.splunk(self, "solar_exp_watts", self.exp_watts)
            
          
########################################
########################################

class ElectricityPacket(NetworkOwlPacket):
    """NetworkOwl electricity packet - upto 6 channels.
    
    Instance variables:
        curr_watts[]        - list of current readings for each channel.
        watts_today[]       - list of daily totals for each channel.
        
        
    XML V1
    ------
        
    <electricity id='xxxx'>
        <signal rssi='-72' lqi='70'/>
        <battery level='100%'/>
        <chan id='0'>
            <curr units='w'>0.00</curr>
            <day units='wh'>0.00</day>
        </chan>
        <chan id='1'>
            <curr units='w'>84.00</curr>
            <day units='wh'>146.96</day>
        </chan>
        <chan id='2'>
            <curr units='w'>0.00</curr>
            <day units='wh'>0.00</day>
        </chan>
    </electricity>
    

    XML V2
    ------
    
    <electricity id='xxxx' ver='2.0'>
        <timestamp>1458313071</timestamp>
        <signal rssi='-58' lqi='4'/>
        <battery level='100%'/>
        <channels>
            <chan id='0'>
                <curr units='w'>342.00</curr>
                <day units='wh'>16456.46</day>
            </chan>
            <chan id='1'>
                <curr units='w'>383.00</curr>
                <day units='wh'>13415.39</day>
            </chan>
            <chan id='2'>
                <curr units='w'>0.00</curr>
                <day units='wh'>0.00</day>
            </chan>
            <chan id='3'>
                <curr units='w'>0.00</curr>
                <day units='wh'>0.00</day>
            </chan>
            <chan id='4'>
                <curr units='w'>0.00</curr>
                <day units='wh'>0.00</day>
            </chan>
            <chan id='5'>
                <curr units='w'>0.00</curr>
                <day units='wh'>0.00</day>
            </chan>
        </channels>
        <property>
            <current>
                <watts>342.00</watts>
                <cost>0.00</cost>
            </current>
            <day>
                <wh>16456.46</wh>
                <cost>101.96</cost>
            </day>
            <tariff>
                <curr_price>0.13</curr_price>
                <block_limit>4294967295</block_limit>
                <block_usage>4686</block_usage>
            </tariff>
        </property>
    </electricity>
    
        
    """
    ########################################
    def __init__(self, plugin, addr, root):
        """Initialise electricity instance variables."""
        NetworkOwlPacket.__init__(self, plugin, addr)
        self.packet_type = "electricity"
        self.curr_watts = [0, 0, 0, 0, 0, 0]
        self.watts_today = [0, 0, 0, 0, 0, 0]
        
        # work out which version of XML we're dealing with & behave accordingly
        self.xml_version = root.get('ver')
         
        if self.xml_version == None:
            # original version of the packet with no version number
            self.plugin.mylogger.log(4, "NetworkOwl: Original XML version")  
            self.valid = True
            
            # get the signal characteristics & battery level      
            sig = root.find('signal')
            self.signal_strength = sig.get('rssi')
            self.signal_quality = sig.get('lqi')
            self.battery_level = root.find('battery').get('level')
                      
            # step through each of the channels - repeats the data for each of the
            # channels supported by the transmitter
            for elem in root.getiterator('chan'):
                channel = int(elem.get('id'))
                curr_watts = elem.find('curr').text
                watts_day = elem.find('day').text
            
                # remove the decimal points
                curr_watts = self.stripDecimals(curr_watts)
            
                self.curr_watts[channel] = curr_watts
                self.watts_today[channel] = watts_day
            
        elif self.xml_version == '2.0':
            # Version 2 of packet
            self.plugin.mylogger.log(4, "NetworkOwl: XML version: %s" % self.xml_version)
            self.valid = True
            
            # get the signal characteristics & battery level      
            sig = root.find('signal')
            self.signal_strength = sig.get('rssi')
            self.signal_quality = sig.get('lqi')
            self.battery_level = root.find('battery').get('level')
                  
            # step through each of the channels - repeats the data for each of the
            # channels supported by the transmitter
            for elem in root.getiterator('chan'):
                channel = int(elem.get('id'))
                curr_watts = elem.find('curr').text
                watts_day = elem.find('day').text
        
                # remove the decimal points
                curr_watts = self.stripDecimals(curr_watts)
        
                self.curr_watts[channel] = curr_watts
                self.watts_today[channel] = watts_day
            
        else:
            # unknown XML format - log error
            self.plugin.mylogger.logError(u"unrecognised electricity packet received")

                
    ########################################
    
    def associate(self):
        """Update Indigo with electricity packet data"""
        NetworkOwlPacket.associate(self)
        self.device.updateStateOnServer("signalStrength", self.signal_strength)
        self.device.updateStateOnServer("signalQuality", self.signal_quality)
        self.device.updateStateOnServer("batteryLevel", self.battery_level)
        
        self.plugin.mylogger.log(4, "ElectricityPacket:associate: Owl Type = %s" % self.owlType)

        if self.owlType == 'pv':
            # single phase usage figures in channel 0
            self.device.updateStateOnServer("usedWattsNow", self.curr_watts[0])
            self.device.updateStateOnServer("usedWattsToday", self.watts_today[0])
            
            self.plugin.mylogger.log(3, "NetworkOwl: using watts: " + self.curr_watts[0])
            
            NetworkOwlPacket.splunk(self, "elec_using_watts", self.curr_watts[0])

        elif owlType == 'lc':
            # 3 phase usage in channels 0-2: ignores channels 3 - 5
            self.device.updateStateOnServer("usedWattsNowPh1", self.curr_watts[0])
            self.device.updateStateOnServer("usedWattsTodayPh1", self.watts_today[0])
            self.device.updateStateOnServer("usedWattsNowPh2", self.curr_watts[1])
            self.device.updateStateOnServer("usedWattsTodayPh2", self.watts_today[1])
            self.device.updateStateOnServer("usedWattsNowPh3", self.curr_watts[2])
            self.device.updateStateOnServer("usedWattsTodayPh3", self.watts_today[2])
            
            self.plugin.mylogger.log(3, "NetworkOwl: Ph1 using watts: " + self.curr_watts[0])
            self.plugin.mylogger.log(3, "NetworkOwl: Ph2 using watts: " + self.curr_watts[1])
            self.plugin.mylogger.log(3, "NetworkOwl: Ph3 using watts: " + self.curr_watts[2])
            
            NetworkOwlPacket.splunk(self, "elec_using_watts_ph1", self.curr_watts[0])
            NetworkOwlPacket.splunk(self, "elec_using_watts_ph2", self.curr_watts[1])
            NetworkOwlPacket.splunk(self, "elec_using_watts_ph3", self.curr_watts[2])


########################################
########################################

class WeatherPacket(NetworkOwlPacket):
    """NetworkOwl weather packet.
    
    Instance variables:
        weather_code    - World Weather Online code representing current weather type.
        weather_text    - textual description of current weather
        temperature     - current temperature
        
    Weather code values defined at:
        http://www.worldweatheronline.com/feed/wwoConditionCodes.txt.
        
    <weather id='xxxx' code='116'>
        <temperature>16.00</temperature>
        <text>Partly Cloudy</text>
    </weather>

    """
    ########################################
    def __init__(self, plugin, addr, root):
        """Initialise weather instance variables."""
        NetworkOwlPacket.__init__(self, plugin, addr)
        self.packet_type = "weather"
        self.weather_code = 0
        self.weather_text = ""
        self.temperature = 0
        
        # work out which version of XML we're dealing with & behave accordingly
        self.xml_version = root.get('ver')
         
        if self.xml_version == None:
            # original version of the packet with no version number
            self.valid = True
  
            self.weather_code = root.get('code')
            self.temperature = root.find('temperature').text
            self.weather_text = root.find('text').text
            
        else:
            # unknown XML format - log error
            self.plugin.mylogger.logError(u"unrecognised weather packet received")

            
    ########################################
    def associate(self):
        """Update Indigo with weather packet data"""
        NetworkOwlPacket.associate(self)
        self.device.updateStateOnServer("weatherCode", self.weather_code)
        self.device.updateStateOnServer("temperature", self.temperature)
        self.device.updateStateOnServer("weatherText", self.weather_text)
            
        self.plugin.mylogger.log(3, "NetworkOwl: weather: " + self.weather_text)  
        
        NetworkOwlPacket.splunk(self, "weather_temp", self.temperature)
        NetworkOwlPacket.splunk(self, "weather_code", self.weather_code)       
            

########################################
########################################

class HeatingPacket(NetworkOwlPacket):
    """NetworkOwl Heating packet.
    
    Will need to adapt in a future version to cope with >1 heating zone
    Create a 'zone' object which holds the details for each zone
    Store in Dict keyed off zone ID
    Poss reuse for hot water (water zone?)
    
    Instance variables:
        temperature         - current temperature
        temp_set_point      - required temperature
        temp_valid_until    - next heating program change
        zone                - heating zone

    XML V1
    ------
    
    <heating id='xxxx'>
        <signal rssi='-55' lqi='50'/>
        <battery level='2990mV'/>
        <temperature until='1371022885' zone='0'>
            <current>21.12</current>
            <required>22.05</required>
        </temperature>
    </heating>
    
    XML V2
    ------
 
    <heating ver='2' id='xxxx'>
        <timestamp>1459524558</timestamp>
        <zones>
            <zone id='2000217' last='1'>
                <signal rssi='-61' lqi='50'/>
                <battery level='2780'/>
                <conf flags='0'/>
                <temperature state='0' flags='4229' until='1371022885' zone='0'>
                    <current>19.75</current>
                    <required>22.05</required>
                </temperature>
            </zone>
        </zones>
    </heating>
   

    """
    ########################################
    def __init__(self, plugin, addr, root):
        """Initialise heating instance variables."""
        NetworkOwlPacket.__init__(self, plugin, addr)
        self.packet_type = "heating"
        self.zone = '0'
        self.temperature = 0
        self.temp_set_point = 0
        self.valid_until = 0
        
        # work out which version of XML we're dealing with & behave accordingly
        self.xml_version = root.get('ver')
         
        if self.xml_version == None:
            # original version of the packet with no version number
            self.plugin.mylogger.log(4, "NetworkOwl: Original XML version")  
            self.valid = True
           
            # get the signal characteristics & battery level      
            sig = root.find('signal')
            self.signal_strength = sig.get('rssi')
            self.signal_quality = sig.get('lqi')
            self.battery_level = root.find('battery').get('level')
        
            # ignoring zone & valid_until for now

            # get the current & required temperatures
            currTemp = root.find('temperature')
            self.temperature = currTemp.find('current').text
            self.temp_set_point = currTemp.find('required').text

        elif self.xml_version == '2':
            # Version 2 of packet
            self.plugin.mylogger.log(4, "NetworkOwl: XML version: %s" % self.xml_version)
            self.valid = True
        
            # Firmware 2.6 introduces support for multiple zones
            # this version only handles a single zone
        
            # step through each of the zones
            for elem in root.getiterator('zone'):
                zone = elem.get('id')
                # get the signal characteristics & battery level      
                sig = elem.find('signal')
                self.signal_strength = sig.get('rssi')
                self.signal_quality = sig.get('lqi')
                self.battery_level = elem.find('battery').get('level')
            
                # get the current & required temperatures                
                currTemp = elem.find('temperature')
                self.temperature = currTemp.find('current').text
                self.temp_set_point = currTemp.find('required').text
            
        else:
            # unknown XML format - log error
            self.plugin.mylogger.logError(u"unrecognised heating packet received")
          

    ########################################
    def associate(self):
        """
        Update Indigo with heating packet data
        Ignore zones in this version
        """
        NetworkOwlPacket.associate(self)
        self.device.updateStateOnServer("heatingTemp", self.temperature)
        self.device.updateStateOnServer("heatingTempSetPoint", self.temp_set_point)
        
        self.plugin.mylogger.log(3, "NetworkOwl: heating at %s, desired %s" % (self.temperature, self.temp_set_point))
        
        NetworkOwlPacket.splunk(self, "heat_temp", self.temperature)

      
########################################
########################################

class HotWaterPacket(NetworkOwlPacket):
    """NetworkOwl HotWater packet.
    
    Instance variables:
        temperature         - current temperature
        temp_set_point      - required temperature
        temp_valid_until    - next heating program change

    XML V1
    ------

    <hot_water id='xxxx'>
        <signal rssi='-61' lqi='49'/>
        <battery level='2990mV'/>
        <temperature until='536917880'>
            <current>20.50</current>
            <required>10.00</required>
        </temperature>
    </hot_water>
    
    XML V2
    ------    
    
    <hot_water ver='2' id='xxxx'>
        <timestamp>1459524537</timestamp>
        <zones>
            <zone id='20005DB' last='1'>
                <signal rssi='-61' lqi='49'/>
                <battery level='2630'/>
                <conf flags='0'/>
                <temperature state='0' flags='4096' until='0'>
                    <current>28.50</current>
                    <required>10.00</required>
                    <ambient>26.25</ambient>
                </temperature>
            </zone>   
        </zones>
    </hot_water>


    """
    ########################################
    def __init__(self, plugin, addr, root):
        """Initialise hot water instance variables."""
        NetworkOwlPacket.__init__(self, plugin, addr)
        self.packet_type = "hot_water"
        self.temperature = 0
        self.temp_set_point = 0
        self.valid_until = 0
        
        # work out which version of XML we're dealing with & behave accordingly
        self.xml_version = root.get('ver')
         
        if self.xml_version == None:
            # original version of the packet with no version number
            self.plugin.mylogger.log(4, "NetworkOwl: Original XML version")  
            self.valid = True
            
            # get the signal characteristics & battery level      
            sig = root.find('signal')
            self.signal_strength = sig.get('rssi')
            self.signal_quality = sig.get('lqi')
            self.battery_level = root.find('battery').get('level')
        
            #ignoring valid_until for now

            # get the current & required temperatures                
            currTemp = root.find('temperature')
            self.temperature = currTemp.find('current').text
            self.temp_set_point = currTemp.find('required').text

        elif self.xml_version == '2':
            # Version 2 of packet
            self.plugin.mylogger.log(4, "NetworkOwl: XML version: %s" % self.xml_version)
            self.valid = True
                
            # Firmware 2.6 introduces support for multiple zones
            # this version only handles a single zone
        
            # step through each of the zones
            for elem in root.getiterator('zone'):
                zone = elem.get('id')
                # get the signal characteristics & battery level      
                sig = elem.find('signal')
                self.signal_strength = sig.get('rssi')
                self.signal_quality = sig.get('lqi')
                self.battery_level = elem.find('battery').get('level')
            
                # get the current & required temperatures                
                currTemp = elem.find('temperature')
                self.temperature = currTemp.find('current').text
                self.temp_set_point = currTemp.find('required').text
            
        else:
            # unknown XML format - log error
            self.plugin.mylogger.logError(u"unrecognised hot water packet received")


    ########################################
    def associate(self):
        """
        Update Indigo with hot water packet data
        Ignore zones in this version
        """
        NetworkOwlPacket.associate(self)
        self.device.updateStateOnServer("hotWaterTemp", self.temperature)
        self.device.updateStateOnServer("hotWaterTempSetPoint", self.temp_set_point)
        
        self.plugin.mylogger.log(3, "NetworkOwl: hot water at %s, desired %s" % (self.temperature, self.temp_set_point))
        
        NetworkOwlPacket.splunk(self, "water_temp", self.temperature)
