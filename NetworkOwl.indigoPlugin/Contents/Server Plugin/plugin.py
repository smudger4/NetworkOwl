#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Add NetworkOwl to Indigo
# Reads solar PV generation, electricity usage, weather, heating & hot water data & updates device states
# Reads 3 phases if device type is Intution-lc
# V1.6  16 January 2018
# https://smudger4.github.io
#
#
# v1.6: repackaged for Indigo Plugin Library - no functional changes
# v1.5: changed logging to use the open source indigoPluginUtils logger
# v1.4: no change
# v1.3: rewritten to replace references to Twisted with more generic networking code, as Twisted no longer supported by Indigo when running on OS X 10.9 (Mavericks) because Twisted libraries were removed from the old version of OS X Python that Indigo relies on.
# v1.2: adds read-only support for hot water & heating controls
# v1.1: extends electricity packet to support 3-phase
# v1.0: initial version
#
# Originally based on example code from Indigo SDK v1.02
# Copyright (c) 2012, Perceptive Automation, LLC. All rights reserved.
# http://www.perceptiveautomation.com
#

import os
import sys
import struct

import indigoPluginUtils

from NetworkOwl import NetworkOwl

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
class Plugin(indigo.PluginBase):
    """Indigo Plugin class, adding NetworkOWL support to Indigo.
    
    Class variables:
        listeningPort   - multicast port we're listening to
        deviceDict      - dictionary of MAC address / Device tuples
        
    """
    listeningPort = None
    deviceDict = {}
    
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.deviceList = []
        self.configRead = False
        self.mylogger = indigoPluginUtils.logger(self)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    ########################################
    def startup(self):
        self.mylogger.log(4, u"startup called")
        self.configRead = self.getConfiguration(self.pluginPrefs)

    ########################################
    def shutdown(self):                     # called after runConcurrentThread() exits
        self.mylogger.log(4, u"shutdown called")
             
    ########################################
    def getConfiguration(self, valuesDict):

        # Tell our logging class to reread the config for level changes
        self.mylogger.readConfig()

        self.mylogger.log(3, u"getConfiguration start")

        return True

        
    ########################################
    def deviceStartComm(self, dev):
        """Initialise Indigo device & reset all server states."""
        self.mylogger.log(4, "Starting device: " + dev.name)
        
        # force re-read of device states from Devices.xml
        dev.stateListOrDisplayStateIdChanged()

        # stash device ID
        if dev.id not in self.deviceList:
            self.deviceList.append(dev.id)
    
        # get MAC address from props
        macAddress = dev.pluginProps["address"] 
        self.mylogger.log(3, "MAC Address: " + macAddress)
                    
        # stash MAC addr & device in a dictionary
        # use MAC addr as key so can find appropriate device to update
        # when receiving data - MAC addr field in network packet
        if macAddress not in self.deviceDict:
            self.deviceDict[macAddress] = dev
            
        # get OWL type from props
        owlType = dev.pluginProps["owlType"]
        self.mylogger.log(3, "Owl Type: %s" % owlType)
        
          
        # reset device states
        dev.updateStateOnServer("networkOwlId", macAddress)
        dev.updateStateOnServer("genWattsNow", '0')
        dev.updateStateOnServer("expWattsNow", '0')
        dev.updateStateOnServer("genWattsToday", '0')
        dev.updateStateOnServer("expWattsToday", '0')
        dev.updateStateOnServer("signalStrength", '0')
        dev.updateStateOnServer("signalQuality", '0')
        dev.updateStateOnServer("batteryLevel", '0')
        dev.updateStateOnServer("usedWattsNow", '0')
        dev.updateStateOnServer("usedWattsToday", '0')
        dev.updateStateOnServer("weatherCode", '0')
        dev.updateStateOnServer("temperature", '0')
        dev.updateStateOnServer("weatherText", '')
        dev.updateStateOnServer("lastUpdated", '')
        dev.updateStateOnServer("usedWattsNowPh1", '0')
        dev.updateStateOnServer("usedWattsTodayPh1", '0')
        dev.updateStateOnServer("usedWattsNowPh2", '0')
        dev.updateStateOnServer("usedWattsTodayPh2", '0')
        dev.updateStateOnServer("usedWattsNowPh3", '0')
        dev.updateStateOnServer("usedWattsTodayPh3", '0')
        dev.updateStateOnServer("networkOwlType", owlType)
        dev.updateStateOnServer("hotWaterTemp", "0")
        dev.updateStateOnServer("hotWaterTempSetPoint", "0")
        dev.updateStateOnServer("heatingTemp", "0")
        dev.updateStateOnServer("heatingTempSetPoint", "0")
            
    ########################################
    def deviceStopComm(self, dev):
        """Device stopping so clean up & remove stored references to it."""
        self.mylogger.log(4, "Stopping device: " + dev.name)
                
        if dev.id in self.deviceList:
            self.deviceList.remove(dev.id)

        # get MAC address from props
        macAddress = dev.pluginProps["address"] 
        self.mylogger.log(4, "MAC Address: " + macAddress)
                    
        if macAddress in self.deviceDict:
            del self.deviceDict[macAddress]

    
    ########################################
    def runConcurrentThread(self):
        """Start the NetworkOwl handler instance.
        
        A new thread is automatically created and runConcurrentThread() is called
        in that thread after startup() has been called. 
    
        runConcurrentThread() should loop forever and only return after self.stopThread
        becomes True. If this function returns prematurely then the plugin host process
        will log an error and attempt to call runConcurrentThread() again after several 
        seconds.
        
        Note that callback methods from the Indigo host (for menu items, UI actions, etc.)
        are executed in a different thread than runConcurrentThread(). 

        
        """
        try:
            indigo.server.log("NetworkOwl: starting listener on port %d" % (NetworkOwl.MULTICAST_PORT,))

            owl = NetworkOwl(self)
            
            self.checkConfig()
            
            sock = owl.startProtocol()
            if sock != None:
                # successfully joined multicast group, now listen for messages
                owl.runProtocol(sock)
            else:
                self.mylogger.logError(u"NetworkOwl plugin failed to join multicast group")

        except self.StopThread:
                # Optionally catch the StopThread exception and do any needed cleanup.
                pass

    ########################################
    def stopConcurrentThread(self):
        """Stop the NetworkOwl handler instance.
        
        """ 
        indigo.PluginBase.stopConcurrentThread(self)

    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """Validate MAC address provided by user - at present only checks if right length."""
        networkOwlID = str(valuesDict["address"])
        if len(networkOwlID)!= 12:
            self.mylogger.logError(u"NetworkOWL ID \"%s\" must be 12 digits long" % networkOwlID)
            errorDict = indigo.Dict()
            errorDict["address"] = "The value of this field must be 12 digits long"
            return (False, valuesDict, errorDict)
        else:
            return True

########################################
    # Validate the pluginConfig window after user hits OK
    # Returns False on failure, True on success
    #
    def validatePrefsConfigUi(self, valuesDict):
        self.mylogger.log(3, u"validating Prefs called")
        errorMsgDict = indigo.Dict()

        # Tell plugin to reread it's config
        self.configRead = False

        # User choices look good, so return True (client will then close the dialog window).
        return (True)
        
    ########################################
    def checkConfig(self):
        self.mylogger.log(4, u"checkConfig called")
        if self.configRead is False:
            if self.getConfiguration(self.pluginPrefs) is True:
                self.configRead = True

            
    ########################################
    def owlTypeChanged(self, valuesDict, typeId, devId):
    #   typeId is the device type specified in the Devices.xml
    #   devId is the device ID - 0 if it's a new device
        self.mylogger.log(4, u"owlTypeChanged called")
        return valuesDict


