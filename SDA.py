import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import pickle as pk
import time


rm = pyvisa.ResourceManager()

# Interface
SDA = rm.open_resource('TCPIP0::192.168.0.3::5025::SOCKET', write_termination='\n')
SDA.read_termination = "\n"

# Workspace
SDA.query("*IDN?")
SDA.query(":WORK:CAT?")
SDA.query(":WORK:STAT?")

# Application Tests
SDA.query("BENCh:SEL:NAME?")
SDA.query("BENCh:APP:CAT?")
SDA.write("BENCh:APP:SEL 'Id-Vd'")
SDA.query("NAME?")
SDA.query("NUMBer? 'VgStart'")
SDA.query("STR? 'Gate'")

# Dilan IV Sweep Test Setup (My favorite)
'Setting the Experiment'

SDA.query(":BENCh:PRES:CAT?")
SDA.write(":BENCh:PRES:SEL 'IV'")
SDA.query(":BENCh:PRES:SET:CAT?")
SDA.write(":BENCh:PRES:SET:SEL 'Dilan IV Sweep'")
SDA.query("BENCh:SEL:NAME?")
SDA.write(":RUN")

'Retrieving DATA'

SDA.write(":RESult:FORMat TXT")
SDA.query(":RESult:FORMat?")
SDA.query(":RESult:FETch:LATest?")
SDA.query(":RES:FORM:ESC?")
SDA.read()

'Analising Data'

def Linear_Regression(xData, yData):
    """
    Linear Fitting. It returns the x,y fitted data, the slope 
    and the intercept.
    """  
    x_sm = sm.add_constant(xData)
    model = sm.OLS(yData, x_sm)
    fit = model.fit()
    n, m = fit.params

    x_fit = np.linspace(xData[0], xData[-1], 30)
    y_fit = n + x_fit * m
    return [x_fit, y_fit, m, n]
def GetData(): 
    """
    Returns the x and y data from the last measurement done in the SDA
    """
    # Getting the data
    SDA.query(":RESult:FETch:LATest?")
    xlist = []
    ylist = []
    while True:  # The whole file is printed line by line, therefore I have to SDA.read() as many times as data points
        try:  # If exception occurs is because the SDA has nothing else to give me. However, the following code gets an error before since the last line that SDA.read() gives doesn't contain an \r character, therefore the r_index definition prompts an error.
            txt_data = SDA.read()
            if not ("\r" in txt_data):
                t_index = txt_data.index("\t")
                x, y = txt_data[:t_index], txt_data[t_index + 1:]
                break
            else:
                t_index, r_index = txt_data.index("\t"), txt_data.index("\r")  # \t and \r list index
                x, y = txt_data[:t_index], txt_data[
                                           t_index + 1:r_index]  # t_index +1 because the whole \t counts as a 1 character
            xlist.append(float(x))  # converting strings into floats
            ylist.append(float(y))
        except:
            print(f"Line could not be processed \n: Line was: {txt_data}")
            # propper execption handling
            break

    x_data, y_data = np.array(xlist), np.array(ylist)
    return np.array([x_data, y_data])
def ResistorAnalisis(name):  
    """
    name = number of the measurement. It must be a number. This function 
    retrieves the data of the IV curve measurement done over a device 
    whose IV curve is linear. It also do the fitting to obtain the associated 
    resistance, stores the data in a biniray written file with name f'Resistor {name}'
    and plot the graph. You must use plt.show() after using this function to see the 
    plot.
    """
    x_data, y_data = GetData()
    x_fit, y_fit, m, n = Linear_Regression(x_data, y_data)

    # Storing DATA
    pk.dump(np.array([x_data, y_data]), open(f'Resistor {name}', 'wb'))

    # Plotting Data
    plt.plot(x_data, y_data * 10 ** 6, "ro", label="data")  # in micro Ampere units
    plt.plot(x_fit, y_fit * 10 ** 6, ls='dashed', label="Linear Regression")
    plt.title(f'R = {round(m ** (-1) / 10 ** 3)} kΩ ', fontsize=10)
    plt.xlabel('Voltage (V)')
    plt.ylabel('I (μA)')
    plt.legend()
    return [x_data, y_data, x_fit, y_fit, m, n]
def ResistorS():  
    """
    This function takes the data from all the files stored using the 
    ResistorsAnalisis function and plot them all in a single plot.
    You need to use plt.show() after using this function to see the 
    plot
    """
    # Getting Data
    xdataS = []
    ydataS = []
    i = 1
    while True:
        try:
            a1, a2 = pk.load(open(f'Resistor {i}', 'rb'))
            xdataS.append(a1)
            ydataS.append(a2)
            i = i + 1
        except:
            break

    # Fitting data
    mS, ns, xfits, yfits = [], [], [], []
    for j in range(len(xdataS)):
        xa, ya, m, n = Linear_Regression(xdataS[j], ydataS[j])
        xfitS.append(xa)
        yfitS.append(ya)
        mS.append(m)
        nS.append(n)

    # Plotting
    for R_ in range(len(xdataS)):
        Resistance = round(mS[R_] ** (-1) / 10 ** 3)  # UNITS [kΩ]
        plt.plot(xdataS[R_], ydataS[R_] * 10 ** 6, "b.", markersize=6)
        plt.plot(xfitS[R_], yfitS[R_] * 10 ** 6, ls='dashed', lw=1, label=f"R = {Resistance} kΩ")
        plt.xlabel('Voltage (V)')
        plt.ylabel('I (μA)')
        plt.legend(fontsize=5)
    plt.title("Julien's Resistors")
    return [xdataS, ydataS, xfitS, yfitS, mS, nS]

# Controling SDA - Single frequency measurement

'Set the measurement'

SDA.write("BENCh:APP:SEL 'Dilan IV Sweep'")
SDA.query("NAME?")

'Set the parameters'

SDA.write("NUMBer 'Vmin'  , -0.5 ")
SDA.write("NUMBer 'Vmax'  ,  1 ")
SDA.write("NUMBer 'Vstep' ,0.1 ")

'Check Parameters'

SDA.query("NUMBer? 'Vmin'")
SDA.query("NUMBer? 'Vmax'")
SDA.query("NUMBer? 'Vstep'")

SDA.timeout == 100

SDA.write(':RUN')
SDA_state = [1,1]
ans = 1
while SDA_state != [0,1]:
    SDA_state[0] = ans
    try:
        SDA.query("*OPC?")
    except:
        ans = 0
        SDA_state[1] = ans
    else:
        ans = 1
        SDA_state[1] = ans
    time.sleep(0.1)

x,y = GetData()
plt.plot(x,y)
plt.show()







