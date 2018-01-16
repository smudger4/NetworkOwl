# listener client for Intuition / Network Owl
# prints XML responses received over multicast
# changed to use Twisted framework
# supports Intuition-pv & Intuition-lc devices
#
# v0.7 Nick 22 April 2016

from NetworkOwl import NetworkOwl
import time

# constants
# set DEBUG to True to see debugging messages in the log
# set OWLADDR to be MAC address of NetworkOwl
# set OWLTYPE to either 'pv' or 'lc' depending on type of OWL being tested
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
        print "intution3: checking config"
        
    def sleep(self, secs):
        print "intuition3: sleeping for %d secs" % secs
        time.sleep(secs)

    def runHarness(self):
        print "intuition3: starting listener on port %d" % (NetworkOwl.MULTICAST_PORT,)
        owl = NetworkOwl(self)
        
        sock = owl.startProtocol()
        if sock != None:
            # successfully joined multicast group, now listen for messages
            owl.runProtocol(sock)
        else:
            self.mylogger.logError(u"Error: NetworkOwl plugin failed to join multicast group")
                        
    
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