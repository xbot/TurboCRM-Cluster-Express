#!/usr/bin/env python

class TCEvent:
    def __init__(self, srcObj):
        self.srcObj = srcObj

class TCDebugEvent(TCEvent): pass
class TCCellEditedEvent(TCEvent):
    def __init__(self, app, cell, usrData):
        TCEvent.__init__(self, app)
        self.app = app
        self.cell = cell
        self.usrData = usrData
class TCUnknownCellEditedEvent(TCCellEditedEvent): pass
class TCSrvTypeChangedEvent(TCCellEditedEvent): pass
class TCHostChangedEvent(TCCellEditedEvent): pass
class TCIPChangedEvent(TCCellEditedEvent): pass
class TCPathChangedEvent(TCCellEditedEvent): pass

if __name__ == '__main__':
    pass
