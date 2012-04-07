#!/usr/bin/env python

class TCException(Exception):
    def __str__(self):
        return str(self.args[0])
