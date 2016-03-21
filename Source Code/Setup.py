import sys
import py2exe
from py2exe.build_exe import py2exe
from distutils.core import setup
import zmq
import os
import matplotlib

sys.setrecursionlimit(5000)


# libzmq.dll is in same directory as zmq's __init__.py
        
os.environ["PATH"] = \
    os.environ["PATH"] + \
    os.path.pathsep + os.path.split(zmq.__file__)[0]
opts = {"py2exe": {
    "includes": ['scipy', 'scipy.integrate', 'scipy.special.*','scipy.linalg.*', "zmq.utils", "zmq.utils.jsonapi", 
                "zmq.utils.strtypes"]}}

setup( windows=['Trading_Module.py'], data_files=matplotlib.get_py2exe_datafiles(),
       options=opts )