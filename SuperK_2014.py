# SuperK laser control
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# from lib.dll_support import superk_aotf
import os
from re import L
from Instruments.instrument import Instrument
import pyvisa
# import visa
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

class WavelengthERROR(Exception):
    """Exception raised for errors in the adressing.
     """
class SuperK_2014(Instrument):
    # Constants
    _host_address = '42';  # Host (PC) address - 0xA2
    _rf_address = '06';  # RF+Select module address - 0x16; address selector to 0x06
    # this is for the super k select / AOTF
    _select_address = '10';  # Select module address - 0x11; address selector to 0x01
    _SK_extreme = '0f'
    # this is for the super k select / AOTF

    _read = '04';  # 0x04
    _write = '05';  # 0x05
    _sot = '0D';  # Start of telegram - \r
    _eot = '0A';  # End of telegram - \n
    _soe = '5E';  # Start of substitution word
    _addVal = 64;  # Value to add for substitution

    def __init__(self, name, address, address_Supk_ext=None, reset=False):
        Instrument.__init__(self, name)  # , tags=['physical']

        self._address = address
        self._testvar = 0
        # self._visa = visa.instrument(self._address, baud_rate=115200, data_bits=8, stop_bits=1, term_chars='\n')
        rm = pyvisa.ResourceManager()
        try:
            self._visa_aotf = rm.open_resource(self._address)
        except Exception as e:
            print('Could not open Superk Select: ' + str(e))
            return -1
        self._visa_aotf.baud_rate = 115200
        self._visa_aotf.stop_bits = StopBits.one
        self._visa_aotf.write_termination = '\n'
        self._visa_aotf.read_termination = '\n'

        dirname = 'C:/ROIC-SW/testsystem-sw/GRACE_software/python/Configuration/Supk_extreme/'
        # filename = 'Supk_extreme_callibration_dot_2mmVis_3mmIr_vis.txt'
        filename_vis = 'SuperK_cal_VISvis.txt'
        cal_area_vis = np.pi * (1e-3) ** 2;

        # filename = 'Supk_extreme_callibration_dot_2mmVis_3mmIr_ir.txt'
        filename_ir = 'SuperK_cal_IRir.txt'
        cal_area_ir = np.pi * (2e-3) ** 2;

        self.calibration_area_ir = cal_area_ir
        self.ir_calibration_file = dirname + filename_ir

        self.calibration_area_vis = cal_area_vis
        self.vis_calibration_file = dirname + filename_vis

        if address_Supk_ext != None:
            self._address_Supk_ext = address_Supk_ext
            self._visa_SuperK = rm.open_resource(self._address_Supk_ext)
            # visa.instrument(self._address_compact,
            #         baud_rate=115200, data_bits=8, stop_bits=1)

        self.add_parameter('power',
                           flags=Instrument.FLAG_GETSET,
                           type=float, minval=0, maxval=100,
                           units='%')

        self.add_parameter('power_density',
                           flags=Instrument.FLAG_SET | Instrument.FLAG_SOFTGET,
                           type=float, minval=0, maxval=10,
                           units='W/m^2')

        self.add_parameter('calibrate',
                           flags=Instrument.FLAG_SET | Instrument.FLAG_SOFTGET,
                           type=bool, doc='If True, power_density has preference over power')

        self.add_parameter('wavelength',
                           flags=Instrument.FLAG_GETSET,
                           type=float, minval=640, maxval=2000,
                           units='nm')

        self.add_parameter('n_wavel',  # I suppose this is supposed to be mixing several WL to increase power.
                           flags=Instrument.FLAG_SET | Instrument.FLAG_SOFTGET,
                           type=float, minval=1, maxval=8,
                           units='')

        self.add_parameter('delta_wavel',
                           flags=Instrument.FLAG_SET | Instrument.FLAG_SOFTGET,
                           type=float, minval=1, maxval=500,
                           units='nm')

        self.add_parameter('output',
                           flags=Instrument.FLAG_GETSET,
                           type=str, option_list=('VIS/NIR', 'NIR/IR'))

        self.add_parameter('state',
                           flags=Instrument.FLAG_GETSET,
                           type=str, option_list=('on', 'off'))

        self.add_parameter('shutter',
                           flags=Instrument.FLAG_GETSET,
                           type=str, option_list=('open', 'closed'))

        self._state_map = {0: 'OFF',
                           1: 'RF ON',
                           2: 'Select ON',
                           3: 'ON'};

        self._output_map = {0: 'VIS/NIR',
                            1: 'NIR/IR'};

        self.add_function('send_command');
        self.add_function('calculate_crc');
        self.add_function('ask_AOTF');
        self.add_function('ask_supk_ext');
        self.add_function('update_power_table');
        self.add_function("set_power_for_n_wavel")
        self.add_function('write_all_registers');
        self.add_function('get_power_calibration');
        self.add_function('get_power_calibration_inv');
        self.add_function('update');

        # Default values
        self.set_n_wavel(1);
        self.set_delta_wavel(10.0);
        self.set_output('VIS/NIR');
        self.set_calibrate(False);
        self.set_power(1);
        self.set_wavelength(1040);
        self.set_state('off');
        # self.set_shutter('close');
        # Register 0x36 is set to 0x0201 on Select
        answer = self.send_command(self._select_address, '05', '36', '0201');

        self.get_all();

    def get_all(self):
        self.get_power();
        self.get_wavelength()
        self.get_output();
        self.get_state();
        # self.get_shutter();

    def ask_AOTF(self, command):
        '''
        Write a command and read value from the device
        '''
        try:
            # result = self._visa_aotf.query(command)
            self._visa_aotf.write_raw(command)
            a = b'00'
            result = ''
            while a != b'\n':
                a = (self._visa_aotf.read_bytes(1))
                result = result + a.hex()
        except Exception as e:
            print('VisaIOError: ' + str(e))
            result = ''
        return result

    def ask_supk_ext(self, command):
        '''
        Write a command and read value from the device (SuperK Compact)
        '''
        try:
            # result = self._visa_SuperK.query(command)
            self._visa_SuperK.write_raw(command)
            a = b'00'
            result = ''
            while a != b'\n':
                a = (self._visa_aotf.read_bytes(1))
                result = result + a.hex()
        except Exception as e:
            print('VisaIOError: ' + str(e))
            result = ''
        return result

    def send_command(self, dest_add, type_in, register_in, data_in, debug=False):
        '''
        Send a command to RF module
        type_in, register_in and data_in are give in HEX string format (without 0x)
        '''
        data_in_end = '';
        data_in_end_crc = '';
        if data_in != "":  # data is little endian! which means LSB first this flips the order:
            for i in reversed(range(0, len(data_in), 2)):
                if data_in[i:i + 2] == self._sot or data_in[i:i + 2] == self._eot or data_in[
                                                                                     i:i + 2] == self._soe or data_in[
                                                                                                              i:i + 2] == self._sot.lower() or data_in[
                                                                                                                                               i:i + 2] == self._eot.lower() or data_in[
                                                                                                                                                                                i:i + 2] == self._soe.lower():
                    data_in_end += self._soe + hex(int(data_in[i:i + 2], 16) + self._addVal)[2:];  # fix reserved bytes
                else:
                    data_in_end += data_in[i:i + 2];
                data_in_end_crc += data_in[i:i + 2];
        crc = self.calculate_crc(dest_add + self._host_address + type_in + register_in + data_in_end_crc);  # calc CRC
        if crc[2:4] == self._sot or crc[2:4] == self._eot or crc[2:4] == self._soe or crc[
                                                                                      2:4] == self._sot.lower() or crc[
                                                                                                                   2:4] == self._eot.lower() or crc[
                                                                                                                                                2:4] == self._soe.lower():
            crc = crc[0:2] + (self._soe + hex(int(crc[2:4], 16) + self._addVal)[2:]) + crc[
                                                                                       4:];  # fix reserved bytes for CRC
        elif crc[4:] == self._sot or crc[4:] == self._eot or crc[4:] == self._soe or crc[
                                                                                     4:] == self._sot.lower() or crc[
                                                                                                                 4:] == self._eot.lower() or crc[
                                                                                                                                             4:] == self._soe.lower():
            crc = crc[0:4] + (self._soe + hex(int(crc[4:], 16) + self._addVal)[2:])
        message = dest_add + self._host_address + type_in + register_in + data_in_end
        message_full = self._sot + message + crc[2:] + self._eot
        answer = self.ask_AOTF(bytes.fromhex(message_full))

        # Decode response
        answer_hex = answer
        answer_hex_filtered = ''
        SpecialChar = 0

        for i in range(0, len(answer_hex), 2):
            if answer_hex[i:i + 2] == self._sot.lower():
                # start of telegram
                continue

            elif answer_hex[i:i + 2] == self._eot.lower():
                # end of telegram and check CRC
                crc = CrcXmodem.calc(unhexlify(answer_hex_filtered))
                if (crc != 0):
                    print("CRC ERROR in receiving answer telegram from {}".format(dest_add))
                    print(f"Send message: {message_full}")
                    print(f"Recived message: {answer}")

            elif answer_hex[i:i + 2] == self._soe or answer_hex[i:i + 2] == self._soe.lower():
                SpecialChar = 1
            else:
                if SpecialChar == 1:
                    # adapt byte for special character case
                    answer_hex_filtered += ("%0.2x" % (int(answer_hex[i:i + 2], 16) - self._addVal))
                    SpecialChar = 0
                else:
                    # no special treatment
                    answer_hex_filtered += answer_hex[i:i + 2]

        data_ordered = '';
        for i in reversed(range(8, len(answer_hex_filtered) - 4, 2)):  # select data bytes and flip data order
            data_ordered += answer_hex_filtered[i:i + 2];
        answer_ordered = answer_hex_filtered[0:8] + data_ordered + answer_hex_filtered[len(answer_hex_filtered) - 4:];
        # Answer is structured like this:
        if debug:
            print("HW exchange:")
            print(message_full)
            print(answer)
            print(answer_ordered)

        return answer_ordered;

    def calculate_crc(self, d_in):
        '''
        Calculates CRC according to CRC-CCITT (Xmodem)
        d_in must be a hex string (without 0x)
        Output is a hex string (with 0x)
        '''
        tmp = hex(CrcXmodem.calc(unhexlify(d_in)));
        if len(tmp) == 5:
            tmp = tmp[0:2] + '0' + tmp[2:];
        elif len(tmp) == 4:
            tmp = tmp[0:2] + '00' + tmp[2:];
        elif len(tmp) == 3:
            tmp = tmp[0:2] + '000' + tmp[2:];
        return tmp;

    def do_get_power(self, channel=None):
        '''
        Get selected power
        '''
        if channel == None:
            channel = 0
        answer = self.send_command(self._rf_address, '04', 'b' + str(channel), '');
        if answer[4:6] != '08':
            print('Power was not retrieved correctly! Answer: ' + answer)
        return int(answer[-10:-4], 16) * 0.1;

    def set_power_for_n_wavel(self, value):
        '''
        Set power output to value (%)
        '''
        if value < 1:
            value = 1
        value_tmp = "%0.4X" % int(value * 10);
        n_wavel_in = self.get_n_wavel();
        for i in range(8):
            if n_wavel_in > i:  # sum the power of the adjacent WL
                answer = self.send_command(self._rf_address, '05', 'b' + str(i), value_tmp);
                if answer[4:6] != '03':
                    print('Power not set correctly! Answer: ' + answer)
            else:
                # set the others to 0
                answer = self.send_command(self._rf_address, '05', 'b' + str(i), "%0.4X" % (0 * 10));

    def do_set_power(self, value, channel=0):
        '''
        Set power output to value (%)
        '''
        value_tmp = "%0.4X" % int(value * 10);
        answer = self.send_command(self._rf_address, '05', 'b' + str(channel), value_tmp);
        if answer[4:6] != '03':
            print('Power not set correctly! Answer: ' + answer)

    def do_get_power_density(self):
        '''
        Get selected power density
        '''
        return self._power_density;

    def do_set_power_density(self, value):
        '''
        Set power density to value (W/m2)
        '''
        if self._testvar != 1:
            self.update('power_density', value);

    def do_get_delta_wavel(self):
        '''
        Get delta_wavel property
        '''
        return self._delta_wavel;

    def do_set_delta_wavel(self, value):
        '''
        Set delta_wavel property
        '''
        self._delta_wavel = value;

    def do_get_n_wavel(self):
        '''
        Get n_wavel property
        '''
        return self._n_wavel;

    def do_set_n_wavel(self, value):
        '''
        Set n_wavel property # this was supposed to be
        '''
        self._n_wavel = value;

    def do_get_calibrate(self):
        '''
        Get calibrate property
        '''
        return self._calibrate;

    def do_set_calibrate(self, value):
        '''
        Set calibrate property
        '''
        self._calibrate = value;

    def do_get_shutter(self):
        '''
        Get Laser (SuperK Compact) shutter state
        '''
        answer = self.ask_supk_ext('sh');
        if answer == 'sh=1':
            return 'open'
        elif answer == 'sh=0':
            return 'closed'
        else:
            print('Unknown shutter state!')
            return 'closed';

    def do_set_shutter(self, value):
        '''
        Set Laser (SuperK Compact) shutter state
        '''
        if value == 'open' or value == 'OPEN':
            answer = self.ask_supk_ext('sh=1');
        elif value == 'closed' or value == 'CLOSED':
            answer = self.ask_supk_ext('sh=0');
        else:
            print('Wrong input parameter. Shutter can only be set to OPEN or CLOSED')

    def do_get_wavelength(self):
        '''
        Get selected wavelength
        '''
        answer = self.send_command(self._rf_address, '04', '90', '');
        if answer[4:6] != '08':
            print('Wavelength not retrieved correctly! Answer: ' + answer)
        return int(answer[-10:-4], 16) * 0.001;

    def do_set_wavelength(self, value):
        '''
        Set wavelength
        '''
        delta_wavel_in = self.get_delta_wavel();

        # Check whether wavelength value is within allowed range
        if self.get_output() == 'VIS/NIR':
            if value < 640 or value > 1100:
                print('Given value is out of range for VIS/NIR output (640-1100nm)!')
                value_tmp = "%0.8X" % int(640 * 1000);
                # value_tmp = hex(int(640 * 1000))
                answer = self.send_command(self._rf_address, '05', '90', value_tmp);
                if answer[4:6] != '03':
                    print('Wavelength not set correctly! Answer: ' + answer)
            else:
                for i in range(8):
                    factor = float(i) * delta_wavel_in;
                    value_tmp = "%0.8X" % int((value + factor) * 1000);
                    # value_tmp = hex(int((value + factor) * 1000))
                    answer = self.send_command(self._rf_address, '05', '9' + str(i), value_tmp);
                    if answer[4:6] != '03':
                        print('Wavelength not set correctly! Answer: ' + answer)
        elif self.get_output() == 'NIR/IR':
            if value < 1155 or value > 2000:
                print('Given value is out of range for NIR/IR output (1155-2000nm)!')
                value_tmp = "%0.8X" % int(1200 * 1000);
                # value_tmp = hex(int(1200 * 1000))
                answer = self.send_command(self._rf_address, '05', '90', value_tmp);
                if answer[4:6] != '03':
                    print('Wavelength not set correctly! Answer: ' + answer)
            else:
                for i in range(8):
                    factor = i * delta_wavel_in;
                    value_tmp = "%0.8X" % int((value + factor) * 1000);
                    # value_tmp = hex(int((value+factor)*1000))
                    answer = self.send_command(self._rf_address, '05', '9' + str(i), value_tmp[2:]);
                    if answer[4:6] != '03':
                        print('Wavelength not set correctly! Answer: ' + answer)
        #        answer = self.send_command(self._rf_address,'05','90',value_tmp);
        #        if answer[4:6] != '03':
        #            print('Wavelength not set correctly! Answer: ' + answer)
        # Update power density / relative power according to selected wavelength
        if self._testvar != 1:
            self.update('wavelength', value);

    def do_set_wavelength_auto(self, value):
        '''
        Set wavelength
        '''
        delta_wavel_in = self.get_delta_wavel();
        if value < 640 or (value > 1100 and value < 1155) or value > 2000:
            raise WavelengthERROR('Given value is out of range! {}'.format(value))
        # Check whether wavelength value is within allowed range
        if (value > 640 and value < 1100):
            if self.get_output() != 'VIS/NIR':
                self.set_output('VIS/NIR')
            for i in range(8):
                factor = float(i) * delta_wavel_in;
                value_tmp = "%0.8X" % int((value + factor) * 1000);
                # value_tmp = hex(int((value + factor) * 1000))
                answer = self.send_command(self._rf_address, '05', '9' + str(i), value_tmp);
                if answer[4:6] != '03':
                    print('Wavelength not set correctly! Answer: ' + answer)
        elif (value > 1155 and value < 2000):
            if self.get_output() != 'NIR/IR':
                self.set_output('NIR/IR')
            for i in range(8):
                factor = i * delta_wavel_in;
                value_tmp = "%0.8X" % int((value + factor) * 1000);
                # value_tmp = hex(int((value+factor)*1000))
                answer = self.send_command(self._rf_address, '05', '9' + str(i), value_tmp[2:]);
                if answer[4:6] != '03':
                    print('Wavelength not set correctly! Answer: ' + answer)
        if self._testvar != 1:
            self.update('wavelength', value);

    def do_get_state(self):
        '''
        Get state
        '''
        answer1 = self.send_command(self._rf_address, '04', '30', '');
        if answer1[4:6] != '08':
            print('State not retrieved correctly! Answer: ' + answer1)
        answer2 = self.send_command(self._select_address, '04', '30', '');
        if answer2[4:6] != '08':
            print('State not retrieved correctly! Answer: ' + answer2)
        if int(answer1[8:10], 16) >= 1 and int(answer2[8:10], 16) == 0:
            return self._state_map[1]
        elif int(answer1[8:10], 16) == 0 and int(answer2[8:10], 16) >= 1:
            return self._state_map[2]
        elif int(answer1[8:10], 16) == 0 and int(answer2[8:10], 16) == 0:
            return self._state_map[0]
        else:
            # answer = self.ask_supk_ext('st');
            answer = 'NOTCONNECTED'
            if answer == 'st=15':
                return self._state_map[3];
            else:
                print('Laser (SuperK Compact) state is not OK. Answer: ' + answer)
                return self._state_map[1];

    def do_set_state(self, value):
        '''
        Set state
        '''
        if value == 'OFF' or value == 'off':
            answer = self.send_command(self._rf_address, '05', '30', '00');
            if answer[4:6] != '03':
                print('State not set correctly! Answer: ' + answer)
            answer = self.send_command(self._select_address, '05', '30', '00');
            if answer[4:6] != '03':
                print('State not set correctly! Answer: ' + answer)
        elif value == 'ON' or value == 'on':
            #            answer = self.send_command(self._select_address,'05','8F','00000000');
            #            answer = self.send_command(self._rf_address,'05','8F','00000000');
            #            if answer[4:6] != '03':
            #                print 'State not set correctly! Answer: ' + answer;
            # Maximum power mode
            #            answer = self.send_command(self._rf_address,'05','31','0000');
            # Optimum power mode
            #            answer = self.send_command(self._rf_address,'05','31','0002');
            # RF driver is enabled
            answer = self.send_command(self._rf_address, '05', '30', '01');
            if answer[4:6] != '03':  # check acknowledge
                print('State not set correctly! Answer: ' + answer)
            # Select is enabled
            sel_enable = '01';  # if self.get_output() == 'VIS/NIR' else '02';
            answer = self.send_command(self._select_address, '05', '30', sel_enable);
            if answer[4:6] != '03':
                print('State not set correctly! Answer: ' + answer)
        else:
            print('Invalid input state: ' + value)

    def do_get_output(self):
        '''
        Get output (VIS/NIR or NIR/IR)
        '''
        answer = self.send_command(self._select_address, '04', '34', '');
        if answer[4:6] != '08':
            print('State not retrieved correctly! Answer: ' + answer)
        if int(answer[8:10], 16) == 1:
            return self._output_map[1];
        elif int(answer[8:10], 16) == 0:
            return self._output_map[0];
        else:
            print('Unknown output!')
            return '';

    def do_set_output(self, value):
        '''
        Set output (VIS/NIR or NIR/IR)
        '''
        if value == 'VIS/NIR':
            # Select output RF switch
            answer = self.send_command(self._select_address, '05', '34', '00');
            if answer[4:6] != '03':
                print('Output not set correctly! Answer: ' + answer)
            # Temperature
            #            answer = self.send_command(self._rf_address,'05','38','00E2');
            # Minimum / Maximum wavelengths (640 - 1100 nm)
            # read crystal parameters and program to rf select
            answer_read = self.send_command(self._select_address, '04', '90', '');  # Minimum Wavelength (640 nm)
            answer = self.send_command(self._rf_address, '05', '34', answer_read[8:-4]);  # Minimum Wavelength (640 nm)
            answer_read = self.send_command(self._select_address, '04', '91', '');  # Minimum Wavelength (640 nm)
            answer = self.send_command(self._rf_address, '05', '35', answer_read[8:-4]);  # Maximum Wavelength (1100 nm)
            # Temperature, frequency coefficients
            answer_read = self.send_command(self._select_address, '04', '92', '');
            answer = self.send_command(self._rf_address, '05', '36', answer_read[8:-4]);
            answer_read = self.send_command(self._select_address, '04', '93', '');
            answer = self.send_command(self._rf_address, '05', '37', answer_read[8:-4]);
            answer = self.send_command(self._rf_address, '05', '38', '00E2');
            answer_read = self.send_command(self._select_address, '04', '94', '');
            answer = self.send_command(self._rf_address, '05', '39', answer_read[8:-4]);
            # answer = self.send_command(self._select_address,'05','8F','00000000');
            # # Read Optimal power table from Select and write in RF driver
            # data = '';
            # for i in range(10):
            # answer_read = self.send_command(self._select_address,'04','95','');
            # if len(answer_read[8:-8])==160:
            # data = data + answer_read[8:-8];
            # else:
            # tmp = '';
            # for i in range(160-len(answer_read[8:-8])):
            # tmp += '0';
            # data = data + tmp + answer_read[8:-8];
            # answer = self.send_command(self._rf_address,'05','8F','00000000');
            # for i in range(10):
            # answer = self.send_command(self._rf_address,'05','3A',data[i*160:i*160+160]);
            # #            print( data);
            self.update_power_table();

        elif value == 'NIR/IR':
            # Select output RF switch
            answer = self.send_command(self._select_address, '05', '34', '01');
            if answer[4:6] != '03':
                print('Output not set correctly! Answer: ' + answer)
            # Temperature
            #            answer = self.send_command(self._rf_address,'05','38','00E2');
            # Minimum / Maximum wavelengths
            answer_read = self.send_command(self._select_address, '04', 'A0', '');  # Minimum Wavelength ( nm)
            answer = self.send_command(self._rf_address, '05', '34', answer_read[8:-4]);  # Minimum Wavelength ( nm)
            answer_read = self.send_command(self._select_address, '04', 'A1', '');  # Minimum Wavelength ( nm)
            answer = self.send_command(self._rf_address, '05', '35', answer_read[8:-4]);  # Maximum Wavelength ( nm)
            # Temperature, frequency coefficients
            answer_read = self.send_command(self._select_address, '04', 'A2', '');
            answer = self.send_command(self._rf_address, '05', '36', answer_read[8:-4]);
            answer_read = self.send_command(self._select_address, '04', 'A3', '');
            answer = self.send_command(self._rf_address, '05', '37', answer_read[8:-4]);
            answer_read = self.send_command(self._select_address, '04', 'A4', '');
            answer = self.send_command(self._rf_address, '05', '39', answer_read[8:-4]);
            # answer = self.send_command(self._select_address,'05','8F','00000000');
            # # Read Optimal power table from Select and write in RF driver
            # data = '';
            # for i in range(10):
            # answer_read = self.send_command(self._select_address,'04','95','');
            # if len(answer_read[8:-8])==160:
            # data = data + answer_read[8:-8];
            # else:
            # tmp = '';
            # for i in range(160-len(answer_read[8:-8])):
            # tmp += '0';
            # data = data + tmp + answer_read[8:-8];
            # answer = self.send_command(self._rf_address,'05','8F','00000000');
            # for i in range(10):
            # answer = self.send_command(self._rf_address,'05','3A', data[i*160:i*160+160]);
            self.update_power_table();
        else:
            print('Invalid output: ' + value)

    def modulate_shutter(self, duration, period):
        per = float(period) / 2;
        times = np.floor(duration / period);
        print(
            "This could be broken since time sleep doesn't need to be precise. could use time.time_ns with a loop to fix")
        for i in range(int(times)):
            if self.get_shutter() == 'closed':
                self.set_shutter('open');
            else:
                self.set_shutter('closed');
            time.sleep(per / 1000);

    def read_all_registers(self, name):
        f = open('Q:\\superk_list_' + name + '.txt', 'a');
        for i in range(256):
            add = hex(i).split('x')[1];
            if len(add) == 1:
                add = '0' + add;
            answer_tmp1 = self.send_command(self._select_address, '04', add, '');
            line_tmp = answer_tmp1 + '\n';
            f.writelines(line_tmp);
        for i in range(256):
            add = hex(i).split('x')[1];
            if len(add) == 1:
                add = '0' + add;
            answer_tmp2 = self.send_command(self._rf_address, '04', add, '');
            line_tmp = answer_tmp2 + '\n';
            f.writelines(line_tmp);
        f.write('\n');
        f.close();

    def update_power_table(self):
        if self.get_output() == 'VIS/NIR':
            # Read Optimal power table from Select and write in RF driver
            answer = self.send_command(self._select_address, '05', '8F', '00000000');
            data = '';
            for i in range(5):
                answer_read = self.send_command(self._select_address, '04', '95', '');
                #                print( answer_read)
                if len(answer_read[8:-8]) == 160:
                    data = data + answer_read[8:-8];
                else:
                    tmp = '';
                    for i in range(160 - len(answer_read[8:-8])):
                        tmp += '0';
                    data = data + tmp + answer_read[8:-8];
            answer = self.send_command(self._select_address, '04', '8F', '');
            #            print( '118F after reading: ' + answer)
            #            print( 'len(data)' + str(len(data)))

            answer = self.send_command(self._rf_address, '05', '8F', '00000000');
            for i in range(5):
                answer = self.send_command(self._rf_address, '05', '3A', data[i * 160:i * 160 + 160]);
            #                print( data[i*160:i*160+160])
            answer = self.send_command(self._rf_address, '04', '8F', '');
        #            print '068F after reading: ' + answer;
        else:
            # Read Optimal power table from Select and write in RF driver
            answer = self.send_command(self._select_address, '05', '8F', '00000000');
            data = '';
            for i in range(5):
                answer_read = self.send_command(self._select_address, '04', 'A5', '');
                #                print answer_read;
                if len(answer_read[8:-8]) == 160:
                    data = data + answer_read[8:-8];
                else:
                    tmp = '';
                    for i in range(160 - len(answer_read[8:-8])):
                        tmp += '0';
                    data = data + tmp + answer_read[8:-8];
            answer = self.send_command(self._select_address, '04', '8F', '');
            #            print '118F after reading: ' + answer;
            #            print 'len(data)' + str(len(data));

            answer = self.send_command(self._rf_address, '05', '8F', '00000000');
            for i in range(5):
                answer = self.send_command(self._rf_address, '05', '3A', data[i * 160:i * 160 + 160]);
            #                print data[i*160:i*160+160];
            answer = self.send_command(self._rf_address, '04', '8F', '');

    #            print '068F after reading: ' + answer;

    def write_all_registers(self, name):
        f_out = open('Q:\\superk_list_' + name + '_wr.txt', 'a');
        with open('Q:\\superk_list_' + name + '.txt', 'r') as f:
            for line in f:
                #                tmp = f.readline()[0:-2];
                tmp = line[0:-1];
                if tmp[4:6] == '08':
                    add = tmp[2:4];
                    reg_add = tmp[6:8];
                    data = tmp[8:-4];
                    if np.mod(len(data), 2) == 0:
                        #                        self.send_command(add,'05',reg_add,data);
                        f_out.writelines('Command: ' + add + '05' + reg_add + data + '\n');
                    else:
                        print('Data length differs from mod 2')
                        print(str(tmp))
                        print(data)
        #                        self.send_command(add,'05',reg_add,'0'+data);
        f_out.write('\n');
        f_out.close();

    def set_irr_calibration(self, path_to_calibration_file, ir_file=None, vis_file=None, area=None):
        '''
        This function sets the calibration data of the SuperK laser and
        returns the relative power (%) needed to reach the required power_density
        power density (W/m2)

        Inputs: path, IR_filename, VIS_file, beam size/powermeter area,

        power meter Area is:  np.pi * (9.5e-3 / 2) ** 2
        '''
        if ir_file is not None:
            if area is not None:
                self.calibration_area_ir = area

            self.ir_calibration_file = os.path.join(path_to_calibration_file, ir_file)

        if vis_file is not None:
            if area is not None:
                self.calibration_area_vis = area

            self.vis_calibration_file = os.path.join(path_to_calibration_file, vis_file)

    def get_power_calibration(self, power_density, wavel, power_density_bool=True):
        '''
        This function reads the calibration data of the SuperK laser and
        returns the relative power (%) needed to reach the required power_density
        power density (W/m2)

        Inputs:
        power_density: Desired output power density in W/m2
        wavel: Wavelength for which the calibration shall be performed
        power_density_bool: if you do not want the power density but the power

        Note that the calibration data files are located in: \\PC0710\\data\\CalibrationData\\
        VIS/NIR: 'cal_curve_SuperK_VIS-NIR.dat'
        NIR/IR: 'cal_curve_SuperK_NIR-IR.dat'
        '''
        laser_output = self.get_output();  # VIS/NIR or NIR/IR
        if laser_output == 'VIS/NIR':
            cal_area = self.calibration_area_vis
            filename = self.vis_calibration_file

        elif laser_output == 'NIR/IR':
            cal_area = self.calibration_area_ir
            filename = self.ir_calibration_file

        # Get calibration data from file
        try:
            f = open(filename, 'r');
        except IOError:
            print('Error: Calibration file ' + filename + ' not found!')
            relative_power = -1;
        else:
            wavelength_list = [];
            relative_power_list = [];
            absolute_power_list = [];
            # Read calibration data
            for line in f:
                if (line[0] != '#') and (len(line) > 5):
                    tmp = line.replace('\n', '').split('\t');
                    wavelength_list.append(float(tmp[0]));
                    relative_power_list.append(float(tmp[1]));
                    if power_density_bool:
                        absolute_power_list.append(float(tmp[2]) / cal_area);  # Converted to power density
                    else:
                        absolute_power_list.append(float(tmp[2]));  # Converted to power density
                    # relative_power_list.append(float(tmp[0]));
                    # wavelength_list.append(float(tmp[1]));
                    # absolute_power_list.append(float(tmp[2])/cal_area);
            f.close();

            absolute_power_list_arr = np.array(absolute_power_list);

            # Get calibration data for the desired wavelength
            rel_power_list = [];  # List of relative powers for desired wavelength
            abs_power_list = [];  # List of absolute powers for desired wavelength
            wavelength_list_unique = np.unique(wavelength_list);
            n_wavel_cal = len(wavelength_list_unique);
            n_power_cal = len(wavelength_list) / n_wavel_cal;
            # Carry out interpolation in wavelength for each power
            for p in range(int(n_power_cal)):
                rel_power_list.append(np.interp(wavel, wavelength_list_unique,
                                                relative_power_list[p * n_wavel_cal:(p + 1) * n_wavel_cal]));
                abs_power_list.append(np.interp(wavel, wavelength_list_unique,
                                                absolute_power_list_arr[p * n_wavel_cal:(p + 1) * n_wavel_cal]));

            # Perform interpolation in power to find needed SuperK power in percentage
            fine_rel_power_list = list(np.arange(0, 100, 0.1));
            fine_abs_power_list = np.interp(fine_rel_power_list, rel_power_list, abs_power_list);
            tmp = abs(np.array(fine_abs_power_list) - power_density);
            relative_power = fine_rel_power_list[list(tmp).index(min(tmp))];

            #            relative_power = np.interp(power_density, abs_power_list, rel_power_list);
            if power_density < min(abs_power_list) or power_density > max(abs_power_list):
                print('Required power density is out of calibrated range for the selected wavelength!')
                print(min(abs_power_list))
                print(max(abs_power_list))

        return relative_power;

    def get_power_calibration_inv(self, power_relative, wavel):
        '''
        This function reads the calibration data of the SuperK laser and
        returns the power density (W/m2) delivered by the selected power_relative
        relative power (%)

        Inputs:
        relative_power: Selected output power in %
        wavel: Wavelength for which the calibration shall be performed

        Note that the calibration data files are located in: \\PC0710\\data\\CalibrationData\\
        VIS/NIR: 'cal_curve_SuperK_VIS-NIR.dat'
        NIR/IR: 'cal_curve_SuperK_NIR-IR.dat'
        '''
        dirname = 'C:/ROIC-SW/testsystem-sw/GRACE_software/python/Configuration/Supk_extreme/'
        laser_output = self.get_output();  # VIS/NIR or NIR/IR
        if laser_output == 'VIS/NIR':
            filename = 'Supk_extreme_callibration_dot_2mmVis_3mmIr_vis.txt'
            filename = 'SuperK_cal_VISvis.txt'
            cal_area = np.pi * (1e-3 / 2) ** 2;

        elif laser_output == 'NIR/IR':

            filename = 'Supk_extreme_callibration_dot_2mmVis_3mmIr_ir.txt'
            filename = 'SuperK_cal_IRir.txt'
            cal_area = np.pi * (2e-3 / 2) ** 2;

        # Calibration is done through a 1mm diameter pinhole in front of the powermeter
        # cal_area = np.pi * (1e-3/2)**2;
        # Calibration is done using the small collimator
        # Calibration is done using big collimator
        # cal_area = np.pi * (0.98e-2/2)**2
        # Get calibration data from file
        try:
            f = open(dirname + filename, 'r');
        except IOError:
            print('Error: Calibration file ' + dirname + filename + ' not found!')
            absolute_power = -1;
        else:
            wavelength_list = [];
            relative_power_list = [];
            absolute_power_list = [];
            # Read calibration data
            for line in f:
                if (line[0] != '#') and (len(line) > 5):
                    tmp = line.replace('\n', '').split('\t');
                    wavelength_list.append(float(tmp[0]));
                    relative_power_list.append(float(tmp[1]));
                    absolute_power_list.append(float(tmp[2]) / cal_area);  # Converted to power density
            f.close();

            # Correct for offset of the powermeter
            absolute_power_list_arr = np.array(absolute_power_list);
            absolute_power_list_arr = absolute_power_list_arr - min(absolute_power_list);

            # Get calibration data for the desired wavelength
            rel_power_list = [];  # List of relative powers for desired wavelength
            abs_power_list = [];  # List of absolute powers for desired wavelength
            wavelength_list_unique = np.unique(wavelength_list);
            n_wavel_cal = len(wavelength_list_unique);
            n_power_cal = int(len(wavelength_list) / n_wavel_cal);
            # Carry out interpolation in wavelength for each power
            for p in range(n_power_cal):
                rel_power_list.append(np.interp(wavel, wavelength_list_unique,
                                                relative_power_list[p * n_wavel_cal:(p + 1) * n_wavel_cal]));
                abs_power_list.append(np.interp(wavel, wavelength_list_unique,
                                                absolute_power_list_arr[p * n_wavel_cal:(p + 1) * n_wavel_cal]));

            # Perform interpolation in power to find delivered SuperK power density for the selected relative power
            absolute_power = np.interp(power_relative, rel_power_list, abs_power_list);
            if absolute_power * cal_area < 40e-9:
                absolute_power = 0;
                print('Power from calibration below calibration limit')
            if power_relative < min(rel_power_list) or power_relative > max(rel_power_list):
                print('Required relative power is out of calibrated range for the selected wavelength!')
                print(min(rel_power_list))
                print(max(rel_power_list))

        return absolute_power;

    def update(self, type, value):
        if type == 'power_density':
            rel_power = self.get_power_calibration(value, self.get_wavelength());
            self._testvar = 1;
            self.set_power(int(rel_power));
            self._testvar = 0;
        elif type == 'wavelength':
            self._testvar = 1;
            if self.get_calibrate() == True:  # Power density is fixed
                rel_power = self.get_power_calibration(self.get_power_density(), value);
                self.set_power(rel_power);
            else:  # Relative power is fixed
                power_density = self.get_power_calibration_inv(self.get_power(), value);
                self.set_power_density(power_density);
            self._testvar = 0;
    
    def SuperK_set_output(self, value):
        """
        Check set_output DocString for more information.
        When setting output, the 'state' must be OFF. This function makes sure of it and also checks if the output and wavelength have 
        been been properly set.
        """
        self.set_state('OFF')
        self.set_output(f'{value}')
        if value == 'VIS/NIR':
            wl = 655
            self.set_wavelength(wl)
            print(f"output = {value}")
            print(f"lambda = {wl}")
        elif value == 'NIR/IR':
            wl = 1211
            self.set_wavelength(wl)
            print(f"output = {value}")
            print(f"lambda = {wl}")
        self.set_state('ON')



    def SuperK_set_state(self,value):
        self.set_state(value)
        print("state =", self.get_state())

    def SuperK_set_wavelength(self,value):
        self.set_wavelength(value)
        print("lambda =", self.get_wavelength())
    def SuperK_set_power(self,value):
        self.set_power(value)
        print("power =", self.get_power())

    def SuperK_get_state(self):
        return self.get_state(self)
    def SuperK_get_output(self):
        return self.get_output(self)
    def SuperK_get_wavelength(self):
        return self.get_wavelength(self)
    def SuperK_get_power(self):
        return self.get_power(self)

