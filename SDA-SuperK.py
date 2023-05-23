import os
from re import L
from instrument import Instrument
import pyvisa
import lib.visa as visa
from pyvisa.constants import StopBits, Parity
import logging
from scipy import *
import numpy as np
from binascii import unhexlify
import crc16 as crc16;
from crccheck.crc import CrcXmodem
import time
import matplotlib.pyplot as plt
import statsmodels.api as sm
import pickle as pk

os.chdir("C:\\Users\\DilanPerezParedes\\OneDrive - Qurv Technologies SL\\Desktop\\Git\\Qurv's Project")
import SuperK_2014
import SDA as B1500A

SuperK = SuperK_2014.SuperK_2014("SuperK", "COM4")
SDA    = B1500A.EasyExpert()