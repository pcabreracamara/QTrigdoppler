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
import traceback

from contextlib import contextmanager
from time import gmtime, strftime
from datetime import datetime, timedelta

from configparser import ConfigParser

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

C = 299792458.

@contextmanager
def socketcontext(*args, **kwargs):
    s = socket.socket(*args, **kwargs)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    yield s
    s.close()

def tx_dopplercalc(ephemdata):
    global I0
    ephemdata.compute(myloc)
    doppler = int(I0 + ephemdata.range_velocity * I0 / C)
    return doppler

def rx_dopplercalc(ephemdata):
    global F0
    ephemdata.compute(myloc)
    doppler = int(F0 - ephemdata.range_velocity * F0 / C)
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
STEP_RX = configur.get('qth','step_rx')
STEP_TX = configur.get('qth','step_tx')
TLEFILE = configur.get('satellite','tle_file')
TLEURL = configur.get('satellite','tle_url')
SATNAMES = configur.get('satellite','amsatnames')
SQFILE = configur.get('satellite','sqffile')
RADIO = configur.get('icom','radio')
CVIADDR = configur.get('icom','cviaddress')
ADDRESS = configur.get('hamlib','address')
PORT = configur.getint('hamlib','port')

F0=0
I0=0
f_cal = 0
i_cal = 0

myloc = ephem.Observer()
myloc.lon = LONGITUDE
myloc.lat = LATITUDE
myloc.elevation = ALTITUDE

SEMAPHORE = True

class Satellite:
    name = ""
    noradid = 0
    amsatname= ""
    downmode = ""
    upmode = ""
    F = 0
    F_init = 0
    I = 0
    I_init = 0
    tledata = ""

class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.counter = 0
        self.my_satellite = Satellite()

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
        self.rxoffsetbox.setMinimum(-800)
        self.rxoffsetbox.setMaximum(800)
        self.rxoffsetbox.setSingleStep(int(STEP_RX))
        self.rxoffsetbox.valueChanged.connect(self.rxoffset_value_changed)
        offset_layout.addWidget(self.rxoffsetbox)

        # 1x Label: TX Offset
        self.txoffsetboxtitle = QLabel("TX Offset:")
        offset_layout.addWidget(self.txoffsetboxtitle)

        # 1x QSlider (TX offset)
        self.txoffsetbox = QSpinBox()
        self.txoffsetbox.setMinimum(-800)
        self.txoffsetbox.setMaximum(800)
        self.txoffsetbox.setSingleStep(int(STEP_TX))
        self.txoffsetbox.valueChanged.connect(self.txoffset_value_changed)
        offset_layout.addWidget(self.txoffsetbox)

         # Start Label
        self.butontitle = QLabel("Press start to connect to Icom radio:")
        self.butontitle.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        button_layout.addWidget(self.butontitle)

        # 1x QPushButton (Start)
        self.Startbutton = QPushButton("Start")
        self.Startbutton.clicked.connect(self.init_worker)
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

        self.threadpool = QThreadPool()
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.recurring_timer)
        self.timer.start()


    def rxoffset_value_changed(self, i):
            global f_cal
            global F0
            f_cal = i
            F0 = self.my_satellite.F_init + f_cal
            self.LogText.append("*** New RX offset: {thenew}".format(thenew=i))
    
    def txoffset_value_changed(self, i):
            global i_cal
            global I0
            i_cal = i
            I0 = self.my_satellite.I_init + i_cal
            self.LogText.append("*** New TX offset: {thenew}".format(thenew=i))
    
    def text_changed(self, satname):
        #   EA4HCF: Let's use PCSat32 translation from NoradID to Sat names, boring but useful for next step.
        #   From NORAD_ID identifier, will get the SatName to search satellite frequencies in dopler file in next step.
        try:
            with open(SATNAMES, 'r') as g:
                namesdata = g.readlines()  
                
            for line in namesdata:
                if re.search(satname, line):
                    self.my_satellite.noradid = line.split(" ")[0].strip()
        except IOError:
            raise MyError()
        
        if self.my_satellite.noradid == 0:
            self.LogText.append("***  Satellite not found in {badfile} file.".format(badfile=SATNAMES))

        #   EA4HCF: Now, let's really use PCSat32 dople file .
        #   From SatName,  will get the RX and TX frequencies.
        try:
            with open(SQFILE, 'r') as h:
                sqfdata = h.readlines()  
                
            for lineb in sqfdata:
                if re.search(satname, lineb):
                    self.my_satellite.F = self.my_satellite.F_init = float(lineb.split(",")[1].strip())*1000
                    self.rxfreq.setText(str(self.my_satellite.F))
                    self.my_satellite.I = self.my_satellite.I_init = float(lineb.split(",")[2].strip())*1000
                    self.txfreq.setText(str(self.my_satellite.I))
                    self.my_satellite.downmode =  lineb.split(",")[3].strip()
                    self.my_satellite.upmode =  lineb.split(",")[4].strip()
                    if self.my_satellite.noradid == 0 or self.my_satellite.F == 0 or self.my_satellite.I == 0:
                        self.Startbutton.setEnabled(False)
                    else:
                        self.Startbutton.setEnabled(True)
                    break
        except IOError:
            raise MyError()

        try:
            with open(TLEFILE, 'r') as f:
                data = f.readlines()   
                
                for index, line in enumerate(data):
                    if str(self.my_satellite.noradid) in line[2:7]:
                        self.my_satellite.tledata = ephem.readtle(data[index-1], data[index], data[index+1])
                        break
        except IOError:
            raise MyError()
        
        if self.my_satellite.tledata == "":
            self.LogText.append("***  Satellite not found in {badfile} file.".format(badfile=TLEFILE))
            self.Startbutton.setEnabled(False)
            return
        else:
            day_of_year = datetime.now().timetuple().tm_yday
            tleage = int(data[index][20:23])
            diff = day_of_year - tleage

            if diff > 7:
                self.LogText.append("***  Warning, your TLE file is getting older: {days} days.".format(days=diff))

    def the_exit_button_was_clicked(self):
        if RADIO == "705":
            try:
                with socketcontext(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((ADDRESS, PORT))
                    #switch off SPLIT operation
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x0F\\0x00\\0xFD 10\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
            except socket.error:
                print("Failed to connect to Rigctld on {addr}:{port} exiting the application.".format(addr=ADDRESS,port=PORT))
        sys.exit()
    
    def the_stop_button_was_clicked(self):
        global SEMAPHORE
        SEMAPHORE = False
        self.LogText.append("Stopped")
        self.Startbutton.setEnabled(True)
    
    def init_worker(self):
        # Pass the function to execute
        self.LogText.append("Connected to Rigctld on {addr}:{port}".format(addr=ADDRESS,port=PORT))
        self.LogText.append("Tracking: {sat_name}".format(sat_name=self.my_satellite.amsatname))
        self.LogText.append("Sat DownLink mode: {sat_mode_down}".format(sat_mode_down=self.my_satellite.downmode))
        self.LogText.append("Sat UpLink mode: {sat_mode_up}".format(sat_mode_up=self.my_satellite.upmode))
        self.LogText.append("Recieve Frequency (F) = {rx_freq}".format(rx_freq=self.my_satellite.F))
        self.LogText.append("Transmit Frequency (I) = {tx_freq}".format(tx_freq=self.my_satellite.I))
        self.LogText.append("RX Frequency Offset = {rxfreq_off}".format(rxfreq_off=f_cal))
        self.LogText.append("TX Frequency Offset = {txfreq_off}".format(txfreq_off=i_cal))
        self.Startbutton.setEnabled(False)

        worker = Worker(self.calc_doppler)

        # Execute
        self.threadpool.start(worker)

    def calc_doppler(self, progress_callback):
        global RADIO
        global CVIADDR
        global SEMAPHORE
        global myloc
        global f_cal
        global i_cal
        global F0
        global I0
        
        try:
            with socketcontext(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ADDRESS, PORT))
                
                if RADIO == "9700":
                    # turn off satellite mode
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x16\\0x5A\\0x00\\0xFD 14\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #turn on scope waterfall
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x1A\\0x05\\0x01\\0x97\\0x01\\0xFD 16\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #show scope during TX
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x1A\\0x05\\0x01\\0x87\\0x01\\0xFD 16\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)
                    #set span = 5kHz
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE2\\0x27\\0x15\\0x00\\0x00\\0x50\\0x00\\0x00\\0x00\\0xFD 22\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set VFOA to USB-D mode
                    s.sendall(b"V VFOA\n")
                    s.sendall(b"M PKTUSB 3000\n")
                    time.sleep(0.2)
                    #set VFOB to USB-D mode
                    s.sendall(b"V VFOB\n")
                    s.sendall(b"M PKTUSB 3000\n")
                    time.sleep(0.2)
                    #return to VFOA
                    s.sendall(b"V VFOA\n")
                    time.sleep(0.2)
                elif RADIO == "705":
                    #show scope during TX
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x1A\\0x05\\0x01\\0x73\\0x01\\0xFD 16\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set span = 5kHz
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x27\\0x15\\0x00\\0x00\\0x50\\0x00\\0x00\\0x00\\0xFD 22\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set SPLIT operation
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x0F\\0x01\\0xFD 10\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    #set VFOA
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x07\\0x00\\0xFD 10\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    if self.my_satellite.downmode == "FM" or self.my_satellite.downmode == "FMN":
                        #set VFOA to FM mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x05\\0x01\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.downmode ==  "USB":
                        #set VFOA to USB mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x01\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.downmode == "DATA-USB":
                        #set VFOA to USB mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x01\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)     
                        #set VFOA to DATA mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x1A\\0x06\\0x01\\0x02\\0xFD 14\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.downmode == "CW":
                        #set VFOA to CW mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x03\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    else:
                        print("*** Downlink mode not implemented yet: {bad}".format(bad=self.my_satellite.downmode))
                        sys.exit()

                    # set initial RX freq
                    F_string = "F {RXF:.0f}\n".format(RXF=self.my_satellite.F_init)
                    s.send(bytes(F_string, 'ascii'))

                    #set VFOB
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x07\\0x01\\0xFD 10\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                    if self.my_satellite.upmode == "FM" or self.my_satellite.upmode == "FMN":
                        #set VFOB to FM mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x05\\0x01\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.upmode == "LSB":
                        #set VFOB to LSB mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x00\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.upmode == "DATA-USB":
                        #set VFOB to LSB mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x01\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)     
                        #set VFOB to DATA mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x1A\\0x06\\0x01\\0x02\\0xFD 14\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.upmode == "DATA-LSB":
                        #set VFOB to LSB mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x00\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)     
                        #set VFOB to DATA mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x1A\\0x06\\0x01\\0x02\\0xFD 14\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    elif self.my_satellite.upmode == "CW":
                        #set VFOB to CW mode
                        cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x06\\0x03\\0x02\\0xFD 12\n"
                        s.sendall(cmds.encode('utf-8'))
                        time.sleep(0.2)
                    else:
                        print("*** Uplink mode not implemented yet: {bad}".format(bad=self.my_satellite.upmode))
                        sys.exit()

                    # set initial TX freq
                    I_string = "F {TXF:.0f}\n".format(TXF=self.my_satellite.I_init)
                    s.send(bytes(I_string, 'ascii'))

                    #return to VFOA
                    cmds = "W \\0xFE\\0xFE\\0x" + CVIADDR + "\\0xE0\\0x07\\0x00\\0xFD 10\n"
                    s.sendall(cmds.encode('utf-8'))
                    time.sleep(0.2)

                F0 = self.my_satellite.F + f_cal
                I0 = self.my_satellite.I + i_cal

                rx_doppler = F0
                tx_doppler = I0

                while SEMAPHORE == True:
                    date_val = strftime('%Y/%m/%d %H:%M:%S', gmtime())
                    myloc.date = ephem.Date(date_val)

                    new_rx_doppler = round(rx_dopplercalc(self.my_satellite.tledata),-1)
                    if new_rx_doppler != rx_doppler:
                        rx_doppler = new_rx_doppler
                        F_string = "F {the_rx_doppler:.0f}\n".format(the_rx_doppler=rx_doppler)  
                        s.send(bytes(F_string, 'ascii'))
                        self.my_satellite.F = rx_doppler
                    
                    new_tx_doppler = round(tx_dopplercalc(self.my_satellite.tledata),-1)
                    if new_tx_doppler != tx_doppler:
                        tx_doppler = new_tx_doppler
                        I_string = "I {the_tx_doppler:.0f}\n".format(the_tx_doppler=tx_doppler)
                        s.send(bytes(I_string, 'ascii'))
                        self.my_satellite.I = tx_doppler

                    time.sleep(1)

        except socket.error:
            print("Failed to connect to Rigctld on {addr}:{port}.".format(addr=ADDRESS,port=PORT))
            sys.exit()
    
    def recurring_timer(self):
        self.rxfreq.setText(str(int(self.my_satellite.F)))
        self.txfreq.setText(str(int(self.my_satellite.I)))

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

## Starts here:
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