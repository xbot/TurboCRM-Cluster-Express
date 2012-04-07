#!/usr/bin/env python

import os
from exception.exceptions import *
from events import *
from eventqueue import TCEventQueue
from library.functions import *

class TCListener():
    ''' Parent class of all listeners
    '''
    eventType = None

    @classmethod
    def isTarget(cls, evt):
        return isinstance(evt, cls.eventType)

    @classmethod
    def processEvent(cls, evt): pass

class TCDebugListener(TCListener):
    ''' Debugging Listener
    '''
    eventType = TCDebugEvent
    
    @classmethod
    def processEvent(cls, evt):
        print evt.srcObj

class TCCellEditedLsnr(TCListener):
    eventType = TCCellEditedEvent
    
    @classmethod
    def processEvent(cls, evt):
        store,newText,path,colNum = evt.usrData[:4]
        cls.beforeStore(store, newText, path, colNum)
        store[path][colNum] = newText
        cls.afterStore(store, newText, path, colNum)

    @staticmethod
    def beforeStore(store, newText, path, colNum): pass

    @staticmethod
    def afterStore(store, newText, path, colNum): pass

class TCUnknownCellEditedLsnr(TCCellEditedLsnr):
    eventType = TCUnknownCellEditedEvent
    
    @classmethod
    def processEvent(cls, evt):
        raise TCException("Unknown cell type !")

class TCSrvTypeChangedLsnr(TCCellEditedLsnr):
    eventType = TCSrvTypeChangedEvent
    
    @classmethod
    def processEvent(cls, evt):
        newKey = None
        store,newText,path,colNum,colKeyNum = evt.usrData
        cStore = evt.cell.get_property('model')
        for row in cStore:
            if newText == row[1]:
                newKey = row[0]
                break
        # If the newText is not found in the store ...
        if newKey is not None:
            store[path][colKeyNum] = newKey
            store[path][colNum] = newText
        else:
            raise TCException(_('Unknown server type !'))

class TCHostChangedLsnr(TCCellEditedLsnr):
    eventType = TCHostChangedEvent
    
    @staticmethod
    def beforeStore(store, newText, path, colNum):
        if not is_hostname(newText):
            raise TCException(_("Invalid hostname !"))

class TCIPChangedLsnr(TCCellEditedLsnr):
    eventType = TCIPChangedEvent
    
    @staticmethod
    def beforeStore(store, newText, path, colNum):
        if not is_ipv4(newText):
            raise TCException(_("Invalid IP address !"))

class TCPathChangedLsnr(TCCellEditedLsnr):
    eventType = TCPathChangedEvent
    
    @staticmethod
    def beforeStore(store, newText, path, colNum):
        if os.path.isabs(newText): return
        if newText.count(':')>0:
            parts = newText.split(':', 1)
            if is_hostname(parts[0]) and os.path.isabs(parts[1]): return
        raise TCException(_("Invalid path !"))

TCEventQueue.registerListener(TCDebugListener)
TCEventQueue.registerListener(TCCellEditedLsnr)
TCEventQueue.registerListener(TCUnknownCellEditedLsnr)
TCEventQueue.registerListener(TCSrvTypeChangedLsnr)
TCEventQueue.registerListener(TCHostChangedLsnr)
TCEventQueue.registerListener(TCIPChangedLsnr)
TCEventQueue.registerListener(TCPathChangedLsnr)

if __name__ == '__main__':
    pass
