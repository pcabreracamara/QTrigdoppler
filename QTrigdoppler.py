# Autor:
#   Original from K8DP Doug Papay (v0.1)
#
#   Adapted v0.3 by EA4HCF Pedro Cabrera


import ephem
import socket
import sys
import math
import time
import re
import urllib.request

from contextlib import contextmanager
from time import gmtime, strftime
from datetime import datetime, timedelta

from configparser import ConfigParser

from PyQt5.QtCore import QSize, Qt

from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

C = 299792458.

@contextmanager
def socketcontext(*args, **kwargs):
    s = socket.socket(*args, **kwargs)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    yield s
    s.close()

def tx_dopplercalc():
    global mysat
    global I0
    mysat.compute(myloc)
    doppler = int(I0 + mysat.range_velocity * I0 / C)
    return doppler

def rx_dopplercalc():
    global mysat
    global F0
    mysat.compute(myloc)
    doppler = int(F0 - mysat.range_velocity * F0 / C)
    return doppler

def MyError():
    print("Failed to find required file!")
    sys.exit()

print("QT Rigdoppler v0.3")

try:
    with open('config.ini') as f:
        f.close()
        configur = ConfigParser()
        configur.read('config.ini')
except IOError:
    raise MyError()


# EA4HCF, params from config.ini
LATITUDE = configur.get('qth','latitude')
LONGITUDE = configur.get('qth','longitude')
ALTITUDE = configur.getfloat('qth','altitude')
TLEFILE = configur.get('satellite','tle_file')
TLEURL = configur.get('satellite','tle_url')
SATNAMES = configur.get('satellite','amsatnames')
SQFILE = configur.get('satellite','sqffile')
RADIO = configur.get('icom','radio')
CVIADDR = configur.get('icom','cviaddress')
ADDRESS = configur.get('hamlib','address')
PORT = configur.getint('hamlib','port')

NORAD_ID = 0
F = 0
I = 0
F0 = 0
I0 = 0
f_cal = 0
i_cal = 0

myloc = ephem.Observer()
myloc.lon = LONGITUDE
myloc.lat = LATITUDE
myloc.elevation = ALTITUDE

SEMAPHORE = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("QT RigDoppler v0.3")
        self.setGeometry(0, 0, 800, 150)

        pagelayout = QVBoxLayout()

        uplayout = QHBoxLayout()
        downlayout = QHBoxLayout()

        pagelayout.addLayout(uplayout)
        pagelayout.addLayout(downlayout)
        
        labels_layout = QVBoxLayout()
        combo_layout = QVBoxLayout()
        offset_layout = QVBoxLayout()
        button_layout = QVBoxLayout()

        combo_layout.setAlignment(Qt.AlignVCenter)

        uplayout.addLayout(combo_layout)
        uplayout.addLayout(labels_layout)
        uplayout.addLayout(offset_layout)
        uplayout.addLayout(button_layout)

        self.sattext = QLabel("Satellite:")
        self.sattext.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        combo_layout.addWidget(self.sattext)

        self.combo1 = QComboBox()
        satlist = []
        with open(SQFILE, 'r') as h:
            sqfdata = h.readlines() 
            for line in sqfdata:
                if ',' and not ";" in line:
                    newitem = str(line.split(",")[0].strip())
                    satlist += [newitem]
        satlist=list(dict.fromkeys(satlist))  
        self.combo1.addItems(['Select one...'])
        self.combo1.addItems(satlist)
        combo_layout.addWidget(self.combo1)

        # 1x Label: RX freq
        self.rxfreqtitle = QLabel("RX freq:")
        labels_layout.addWidget(self.rxfreqtitle)

        self.rxfreq = QLabel("0")
        labels_layout.addWidget(self.rxfreq)

        # 1x Label: TX freq
        self.txfreqtitle = QLabel("TX freq:")
        labels_layout.addWidget(self.txfreqtitle)

        self.txfreq = QLabel("0")
        labels_layout.addWidget(self.txfreq)

        # 1x Label: RX Offset
        self.rxoffsetboxtitle = QLabel("RX Offset:")
        offset_layout.addWidget(self.rxoffsetboxtitle)

        # 1x QSlider (RX offset)
        self.rxoffsetbox = QSpinBox()
        self.rxoffsetbox.setMinimum(-3000)
        self.rxoffsetbox.setMaximum(3000)
        self.rxoffsetbox.setSingleStep(1)
        self.rxoffsetbox.valueChanged.connect(self.rxoffset_value_changed)
        offset_layout.addWidget(self.rxoffsetbox)

        # 1x Label: TX Offset
        self.txoffsetboxtitle = QLabel("TX Offset:")
        offset_layout.addWidget(self.txoffsetboxtitle)

        # 1x QSlider (TX offset)
        self.txoffsetbox = QSpinBox()
        self.txoffsetbox.setMinimum(-3000)
        self.txoffsetbox.setMaximum(3000)
        self.txoffsetbox.setSingleStep(1)
        self.txoffsetbox.valueChanged.connect(self.txoffset_value_changed)
        offset_layout.addWidget(self.txoffsetbox)

         # Start Label
        self.butontitle = QLabel("Press start to connect to Icom radio:")
        self.butontitle.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        button_layout.addWidget(self.butontitle)

        # 1x QPushButton (Start)
        self.Startbutton = QPushButton("Start")
        self.Startbutton.clicked.connect(self.the_start_button_was_clicked)
        self.combo1.currentTextChanged.connect(self.text_changed) 
        button_layout.addWidget(self.Startbutton)

        # 1x QPushButton (Stop)
        self.Stopbutton = QPushButton("Stop")
        self.Stopbutton.clicked.connect(self.the_stop_button_was_clicked)
        button_layout.addWidget(self.Stopbutton)

        # Exit Label
        self.exitbutontitle = QLabel("Disconect and exit:")
        self.exitbutontitle.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        button_layout.addWidget(self.exitbutontitle)

        # 1x QPushButton (Exit)
        self.Exitbutton = QPushButton("Exit")
        self.Exitbutton.setCheckable(True)
        self.Exitbutton.clicked.connect(self.the_exit_button_was_clicked)
        button_layout.addWidget(self.Exitbutton)

        # Output log
        self.LogText = QTextEdit()
        self.LogText.setReadOnly(True)
        self.LogText.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        downlayout.addWidget(self.LogText)
        
        container = QWidget()
        container.setLayout(pagelayout)
        self.setCentralWidget(container)

    def rxoffset_value_changed(self, i):
            global f_cal
            f_cal = i
            self.LogText.append("*** New RX offset: {thenew}".format(thenew=i))
    
    def txoffset_value_changed(self, i):
            global i_cal
            i_cal = i
            self.LogText.append("*** New TX offset: {thenew}".format(thenew=i))
    
    def text_changed(self, satname):
        global NORAD_ID
        #   EA4HCF: Let's use PCSat32 translation from NoradID to Sat names, boring but useful for next step.
        #   From NORAD_ID identifier, will get the SatName to search satellite frequencies in dopler file in next step.
        try:
            with open(SATNAMES, 'r') as g:
                namesdata = g.readlines()  
                
            for line in namesdata:
                if re.search(satname, line):
                    NORAD_ID=line.split(" ")[0].strip()
        except IOError:
            raise MyError()
        
        if NORAD_ID == 0:
            self.LogText.append("***  Satellite not found in {badfile} file.".format(badfile=SATNAMES))

        #   EA4HCF: Now, let's really use PCSat32 dople file .
        #   From SatName,  will get the RX and TX frequencies.
        try:
            with open(SQFILE, 'r') as h:
                sqfdata = h.readlines()  
                
            for lineb in sqfdata:
                if re.search(satname, lineb):
                    F = float(lineb.split(",")[1].strip())*1000
                    self.rxfreq.setText(str(int(F)))
                    I = float(lineb.split(",")[2].strip())*1000
                    self.txfreq.setText(str(int(I)))
                    # ToDo: MANAGE and DISPLAY SAT Down&Up MODE
                    MODEDOWN =  lineb.split(",")[3].strip()
                    MODEUP =  lineb.split(",")[4].strip()
                    if NORAD_ID == 0 or F == 0 or I == 0:
                        self.Startbutton.setEnabled(False)
                    else:
                        self.Startbutton.setEnabled(True)
                    break
        except IOError:
            raise MyError()

    def the_start_button_was_clicked(self):
        global F
        global I
        global F0
        global I0
        global f_cal
        global i_cal
        global mysat
        global RADIO
        global CVIADDR
        global NORAD_ID
        global SEMAPHORE
        
        F = float(self.rxfreq.text())
        I = float(self.txfreq.text())

        F0 = float(self.rxfreq.text()) + float(self.rxoffsetbox.text())
        I0 = float(self.txfreq.text()) + float(self.txoffsetbox.text())

        mysat = ""

        try:
            with open(TLEFILE, 'r') as f:
                data = f.readlines()   
                
                for index, line in enumerate(data):
                    if NORAD_ID in line[2:7]:
                        mysat = ephem.readtle(data[index-1], data[index], data[index+1])
                        break
        except IOError:
            raise MyError()
        
        if mysat == "":
            self.LogText.append("***  Satellite not found in {badfile} file.".format(badfile=TLEFILE))
            self.Startbutton.setEnabled(False)
            return
        else:
            day_of_year = datetime.now().timetuple().tm_yday
            tleage = int(data[index][20:23])
            diff = day_of_year - tleage

            if diff > 7:
                self.LogText.append("***  Warning, your TLE file is getting older: {days} days.".format(days=diff))
   
        try:
            with socketcontext(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ADDRESS, PORT))
                
                self.LogText.append("Connected to Rigctld on {addr}:{port}".format(addr=ADDRESS,port=PORT))
                self.LogText.append("Tracking: {sat_name}".format(sat_name=mysat.name))
                self.LogText.append("Recieve Frequency (F) = {rx_freq}".format(rx_freq=F))
                self.LogText.append("Transmit Frequency (I) = {tx_freq}".format(tx_freq=I))
                self.LogText.append("RX Frequency Offset = {rxfreq_off}".format(rxfreq_off=f_cal))
                self.LogText.append("TX Frequency Offset = {txfreq_off}".format(txfreq_off=i_cal))

                self.Startbutton.setEnabled(False)
                
                if RADIO == "9700":
                    # turn off satellite mode
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x16\\0x5A\\0x00\\0xFD 14\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #turn on scope waterfall
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x1A\\0x05\\0x01\\0x97\\0x01\\0xFD 16\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #show scope during TX
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x1A\\0x05\\0x01\\0x87\\0x01\\0xFD 16\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #set span = 5kHz
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x27\\0x15\\0x00\\0x00\\0x50\\0x00\\0x00\\0x00\\0xFD 22\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set VFOA to USB-D mode
                    ###s.sendall(b"V VFOA\n")
                    ###s.sendall(b"M PKTUSB 3000\n")
                    time.sleep(0.2)
                    #set VFOB to USB-D mode
                    ###s.sendall(b"V VFOB\n")
                    ###s.sendall(b"M PKTUSB 3000\n")
                    time.sleep(0.2)
                    #return to VFOA
                    ###s.sendall(b"V VFOA\n")
                    time.sleep(0.2)
                elif RADIO == "705":
                    #turn on scope waterfall
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x27\\0x10\\0x01\\0xFD 12\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #turn on scope waveform
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x27\\0x11\\0x01\\0xFD 12\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #show scope during TX
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x1A\\0x05\\0x01\\0x73\\0x01\\0xFD 16\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set span = 5kHz
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x27\\0x15\\0x00\\0x00\\0x50\\0x00\\0x00\\0x00\\0xFD 22\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set VFOA
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x07\\0x00\\0xFD 10\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set VFOA to USB mode
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x01\\0x02\\0xFD 12\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    # set initial RX freq
                    F_string = "F {RXF:.0f}\n".format(RXF=F)
                    s.send(bytes(F_string, 'ascii'))

                    #set VFOB
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x07\\0x01\\0xFD 10\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set VFOB to USB mode
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x01\\0x02\\0xFD 12\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    # set initial TX freq
                    I_string = "F {TXF:.0f}\n".format(TXF=I)
                    s.send(bytes(I_string, 'ascii'))

                    #set SPLIT operation
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x0F\\0x01\\0xFD 10\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #return to VFOA
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x07\\0x00\\0xFD 10\n"
                    ###s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                rx_doppler = F0
                tx_doppler = I0
                step_size = 10.

                while SEMAPHORE == True:
                    date_val = strftime('%Y/%m/%d %H:%M:%S', gmtime())
                    myloc.date = ephem.Date(date_val)

                    new_rx_doppler = round(rx_dopplercalc(),-1)
                    if new_rx_doppler != rx_doppler:
                        rx_doppler = new_rx_doppler
                        F_string = "F {rx_doppler:.0f}\n".format(rx_doppler=rx_doppler)  
                        self.rxfreq.setText(str(int(rx_doppler)))  
                        ###s.send(bytes(F_string, 'ascii'))
                        time.sleep(0.2)
                        self.LogText.append(F_string.strip())
                    
                    new_tx_doppler = round(tx_dopplercalc(),-1)
                    if new_tx_doppler != tx_doppler:
                        tx_doppler = new_tx_doppler
                        I_string = "I {tx_doppler:.0f}\n".format(tx_doppler=tx_doppler)
                        self.txfreq.setText(str(int(tx_doppler)))
                        ###s.send(bytes(I_string, 'ascii'))
                        self.LogText.append(I_string.strip())
                        time.sleep(0.2)

                    QApplication.processEvents()

        except socket.error:
            self.LogText.append("Failed to connect to Rigctld on {addr}:{port}".format(addr=ADDRESS,port=PORT))
            sys.exit()

    def the_exit_button_was_clicked(self):
        sys.exit()
    
    def the_stop_button_was_clicked(self):
        global SEMAPHORE
        SEMAPHORE = False
        self.LogText.append("Stopped")
        self.Startbutton.setEnabled(True)

if RADIO != "9700" and RADIO != "705":
    print("***  Icom radio not supported: {badmodel}".format(badmodel=RADIO))
    sys.exit()

socket.setdefaulttimeout(15)

try:
   urllib.request.urlretrieve(TLEURL, TLEFILE)
except Exception as e:
   print("***  Unable to download TLE file: {theurl}".format(theurl=TLEURL))

app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()