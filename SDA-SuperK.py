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
# import crc16 as crc16;
from crccheck.crc import CrcXmodem
import time
import matplotlib.pyplot as plt
# import statsmodels.api as sm
import pickle as pk
from SDA import EasyExpert
from SuperK_2014 import SuperK_2014



class SuperSDA():
    def __init__(self):
        self.SDA    = EasyExpert.__init__(self)
        self.SuperK = SuperK_2014.__init__(self, "SuperK", "COM4")
        self.visa.timeout = 300

    def LambdaDependent_Measurement(self, lo = 1200, lf = 1500, step = 100):
        LambdaRange = np.arange(lo, lf, step)
        Data = {}

        for values in LambdaRange:
            self.SDA.run()
            state = [1, 1]
            while state != [0, 1]:
                state[0] = state[1]
                try:
                    self.SDA.OPC()
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

            Data[f"{values}"] = self.SDA.GetData()

        for values in LambdaRange:
            x, y = Data[f"{values}"]
            plt.plot(x, y * 10 ** 6)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Current (μA)")

        return Data, LambdaRange

SuperSDA_ = SuperSDA()

SuperSDA_.SDA.idn()
SuperSDA_.SDA.select_measurement("Dilan IV Sweep")
SuperSDA_.SDA.set_parameters(-0.5,0.5,0.1)
SuperSDA_.SuperK.SuperK_set_output("NIR/IR")
SuperSDA_.SuperK.SuperK_set_wavelength(1500)
SuperSDA_.SuperK.SuperK_set_power(100)

----------------------------------------------------------------
Data, LambdaRange = SuperSDA_.LambdaDependent_Measurement()

for values in LambdaRange:
    x, y = Data[f"{values}"]
    plt.plot(x, y * 10 ** 6)
plt.xlabel("Voltage (V)")
plt.ylabel("Current (μA)")
plt.yscale("linear")
