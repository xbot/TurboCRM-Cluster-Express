#!/usr/bin/python
# -*- coding: utf-8 -*-
from cx_Freeze import setup,Executable
 
includefiles = [('cluster.sh','cluster.sh')]
includes = []
excludes = []
packages = []
 
setup(
    name = 'tcexpr',
    version = '0.1',
    description = 'TurboCRM cluster express',
    author = 'Lenin Lee',
    author_email = 'lenin.lee@gmail.com',
    options = {
        'build_exe':{
            'excludes':excludes,
            'packages':packages,
            'include_files':includefiles,
            'compressed':True
        }
    },
    executables = [Executable('tcexpr.py')]
)
