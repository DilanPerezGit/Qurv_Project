import os
from re import L
from Instruments.instrument import Instrument
import pyvisa
import Instruments.lib.visa as visa
from pyvisa.constants import StopBits, Parity
import logging
from scipy import *
import numpy as np
from binascii import unhexlify
# import crc16 as crc16;
from crccheck.crc import CrcXmodem
import time
import matplotlib.pyplot as plt
# import statsmodels.api as sm
import pickle as pk
from Instruments.SDA import EasyExpert
from Instruments.SuperK_2014 import SuperK_2014



class SuperSDA(EasyExpert,SuperK_2014):
    def __init__(self, SuperK_name = "SuperK", SuperK_adress = "COM4"):
        EasyExpert.__init__(self)
        SuperK_2014.__init__(self, SuperK_name, SuperK_adress)

    def LambdaDependent_Measurement(self, lo = 1200, lf = 1500, step = 100):
        LambdaRange = np.arange(lo, lf, step)
        SuperSDA_.visa.timeout = 300
        Data = {}

        for values in LambdaRange:
            self.SDA_run()
            state = [1, 1]
            while state != [0, 1]:
                state[0] = state[1]
                try:
                    self.SDA_OPC()
                except:
                    state[1] = 0
                else:
                    state[1] = 1
                time.sleep(0.1)

            while True:
                try:
                    self.visa.read()
                except:
                    break

            Data[f"{values}"] = self.SDA_GetData()

        for values in LambdaRange:
            x, y = Data[f"{values}"]
            plt.plot(x, y * 10 ** 6)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Current (μA)")

        return Data









SuperSDA_ = SuperSDA()

SuperSDA_.SDA_idn()
SuperSDA_.SDA_select_measurement("Dilan IV Sweep")
SuperSDA_.SDA_set_parameters(-0.5,0.5,0.1)
SuperSDA_.SuperK_set_output("NIR/IR")
SuperSDA_.SuperK_set_wavelength(1500)
SuperSDA_.SuperK_set_power(100)

SuperSDA_.SuperK
----------------------------------------------------------------
Data = SuperSDA_.LambdaDependent_Measurement()



LambdaRange = np.arange(1200,2000,200)
for values in LambdaRange:
    x, y = Data[f"{values}"]
    plt.plot(x, y * 10 ** 6)
plt.xlabel("Voltage (V)")
plt.ylabel("Current (μA)")
plt.yscale("linear")

"""
I am gonna add the label SuperK to the rest of the functions

Issue 1: sometimes the SDA get stuck when querying him sth and if you want to query him another thing
         it will return the pending querys. To solve this issue I am currently using SDA.read() which
         reads one by one the pending things. Therefore.   
        
"""