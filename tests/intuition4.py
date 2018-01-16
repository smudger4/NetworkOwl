# debug client for Intuition / Network Owl
# parse debug data
#
# v0.2 Nick 28 March 2016

from NetworkOwl import NetworkOwl

# constants
# set DEBUG to True to see debugging messages in the log
# set OWLADDR to be MAC address of NetworkOwl
# set OWLTYPE to either 'pv' or 'lc' depending on type of OWL being tested
# set SPLUNK to either 'Yes' or 'No' depending on type of logging required
DEBUG = True
OWLADDR = 'OWL ADDR HERE'
OWLTYPE = 'pv'


class logger(object):

	def __init__(self, plugin):
		self.plugin = plugin
		self.logLevel = None
		self.readConfig()

	def readConfig(self):
		kLogLevelList = ['None', 'Normal', 'Verbose', 'Debug', 'Intense Debug']

		# Save current log level
		oldLevel = self.logLevel
		# Get new log level from prefs, default to 1 if not found
		self.logLevel = 1

		# Validate log level
		if self.logLevel > 4:
			self.logLevel = 1

		# Enable debugging?
		if self.logLevel > 2:
			self.plugin.debug = True
		else:
			self.plugin.debug = False

		# If this is the first run
		if(oldLevel is None):
			self.log(1, "Log level preferences are set to \"%s\"." % kLogLevelList[self.logLevel])
		# or are we just checking for a change in log level
		elif oldLevel != self.logLevel:
			self.log(1, "Log level preferences changed to \"%s\"." % kLogLevelList[self.logLevel])

	def log(self, level, logMsg):
		if level <= self.logLevel:
			if level < 3:
				print logMsg
			else:
				print "debug: %s" % logMsg

	def logError(self, logMsg):
		print "error: %s" % logMsg


class testHarness:
    deviceDict = {}
    stopThread = False;

    def __init__(self, address, owlType):
        dev = dummyDevice(address, owlType)
        self.deviceDict[address] = dev
        self.mylogger = logger(self)
        
    def checkConfig(self):
        print "intution4: checking config"

    def runHarness(self):
        print "intuition4: loading debug packet"
        owl = NetworkOwl(self)
        
        sock = owl.startProtocol()
        if sock != None:
            # successfully joined multicast group, now pretend to have received a message
            myPacket = "<electricity id='443719000492'><signal rssi='-66' lqi='54'/><battery level='100%'/><chan id='0'><curr units='w'>661.00</curr><day units='wh'>11860.45</day></chan><chan id='1'><curr units='w'>101.00</curr><day units='wh'>3194.92</day></chan><chan id='2'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan></electricity>"
            
            martinPacket = "<electricity id='443719000492' ver='2.0'><timestamp>1458313071</timestamp><signal rssi='-58' lqi='4'/><battery level='100%'/><channels><chan id='0'><curr units='w'>342.00</curr><day units='wh'>16456.46</day></chan><chan id='1'><curr units='w'>383.00</curr><day units='wh'>13415.39</day></chan><chan id='2'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan><chan id='3'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan><chan id='4'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan><chan id='5'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan></channels><property><current><watts>342.00</watts><cost>0.00</cost></current><day><wh>16456.46</wh><cost>101.96</cost></day><tariff><curr_price>0.13</curr_price><block_limit>4294967295</block_limit><block_usage>4686</block_usage></tariff></property></electricity>"
            
            crapPacket = "<electricity id='443719000492' ver='3.0'><timestamp>1458313071</timestamp><signal rssi='-58' lqi='4'/><battery level='100%'/><channels><chan id='0'><curr units='w'>342.00</curr><day units='wh'>16456.46</day></chan><chan id='1'><curr units='w'>383.00</curr><day units='wh'>13415.39</day></chan><chan id='2'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan><chan id='3'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan><chan id='4'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan><chan id='5'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan></channels><property><current><watts>342.00</watts><cost>0.00</cost></current><day><wh>16456.46</wh><cost>101.96</cost></day><tariff><curr_price>0.13</curr_price><block_limit>4294967295</block_limit><block_usage>4686</block_usage></tariff></property></electricity>"

            

            owl.processDataPacket(myPacket)
            owl.processDataPacket(martinPacket)
            owl.processDataPacket(crapPacket)
        else:
            self.debugLog("testHarness: failed to join multicast group, stopping...")
                        
    
class dummyDevice:
    owlAddr = None
    states = {}

    def __init__(self, address, owlType):
        owlAddr = address
        self.states["networkOwlType"] = owlType
        print ("Created dummy %s device with address %s" % (owlType, owlAddr))
                
    def updateStateOnServer(self, name, state):
        print "Updating state of %s to %s" % (name, state)
     
def main():
    harness = testHarness(OWLADDR, OWLTYPE)
    harness.runHarness()

if __name__ == "__main__":
    main()