#!/usr/bin/env python
import cPickle as pickle
from netifaces import interfaces, ifaddresses, AF_INET

(COL_COMBO_KEY,COL_COMBO_VAL,COL_HOST,COL_IP,COL_PATH,COL_ROW_EDITABLE,COL_PATH_EDITABLE) = range(7)

class Schema(object):
    pswd = ''

    def __init__(self, servers=[], version=None):
        self.servers = servers
        self.version = version
        self.path = None

    def loadStore(self, store):
        self.servers = [[l for l in r] for r in store]

    def save(self):
        f = open(self.path, 'w')
        pickle.dump(self, f, pickle.HIGHEST_PROTOCOL)
        f.close()

    @staticmethod
    def load(path):
        f = open(path, 'r')
        content = pickle.load(f)
        f.close()
        content.setPath(path)
        return content

    def getPath(self):
        return self.path
    def setPath(self, path):
        self.path = path

    def getFileSrv(self, strict=True):
        ''' Return the row holding the file server
        The master server will be returned only if there is no file server 
        and the 'strict' parameter is False.
        '''
        for srv in self.servers:
            if srv[COL_COMBO_KEY]=='filesrv':
                return srv
        if strict is True: return None
        else: return self.getMasterSrv()
    def getMasterSrv(self):
        ''' Return the row holding the master server
        '''
        for srv in self.servers:
            if srv[COL_COMBO_KEY]=='master':
                return srv
        return None

    def getMySelf(self):
        ''' Return the row holding the information of the current machine,
        Return None if no ip addresses are found among the schema.
        '''
        ipaddrs = []
        for ifaceName in interfaces():
            addrs = [i['addr'] for i in ifaddresses(ifaceName).setdefault(AF_INET, [{'addr':None}])]
            ipaddrs.extend(addrs)
        try:
            ipaddrs.remove(None)
            ipaddrs.remove('127.0.0.1')
        except ValueError, e:
            pass
        for srv in self.servers:
            if ipaddrs.count(srv[COL_IP])>0: return srv
        return None

    def setFileSrvPswd(self, pswd):
        self.pswd = pswd

    def getFileSrvPswd(self):
        return self.pswd
