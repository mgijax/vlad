#
# vladCmd.py
# 
# Simple wrapper for running Vlad from the command line.
#
import sys
from libvlad import VladCGI

VladCGI().go(sys.argv)

