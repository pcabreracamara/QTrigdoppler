# QT RigDoppler v0.3

Based on K8DP Doug Papay rigdoppler (@K8DP_Doug)  
Adapted v0.3 and QT by EA4HCF Pedro Cabrera (@PCabreraCamara)  
  
RigDoppler is a very simple Python3 script to correct doppler effect in radio satellites using Icom rigs connected to a computer.  
  
## Requeriments:  
    1) Python3  
    2) Python3 modules
       pip3 install ephem
       pip3 install PyQt5
       pip3 install urllib3
    3) HamLib (https://hamlib.github.io/)  
  
Support files and download links:  

    1) TLE ephemerides file. (Exmple: https://www.pe0sat.vgnet.nl/satellite/tle/)   
    2) AmsatNames.txt (https://www.ea5wa.com/satpc32/archivos-auxiliares-de-satpc32)   
    3) dopler.sqf (https://www.ea5wa.com/satpc32/archivos-auxiliares-de-satpc32)  

  
AmsatNames.txt and dopler.sqf are wide and well known files used by PCSat32 software, so can be reused in the same computer.  

## v0.3 Limitations:
    1) CV-I commands supports both Icom 9700 and Icom 705 radios.
    2) Donwlink and Uplink modulations are not processed for Icom 9700, only USB Data modulation is set for both Downlink and Uplink VFOs (GreenCube).
    ### v0.3 ToDo List:
    1) Improve error handling, detect and correct bugs. 
    2) Let me know if you have something else in mind.
    
## Basic Configuration:
    1) Edit *config.ini* file and set your coordinates and altitude in [qth] section:
    
        ;rigdoppler configuration file
        [qth]
        ;station location
        latitude = 48.188
        longitude = -5.708
        altitude = 70

    2) Set your radio, 9700 or 705. Optionally set the CV-I address:

        ;Icom radio model and CV-I address
        [icom]
        ; Acepted models are 705 or 9700
        radio = 705
        cviaddress = A4
  
## Operation:  
    1) Open TCP connection from your computer to Icom rig using HamLib *rigctld* command:

      Unix/Linux:
      Icom 9700: rigctld -m 3081 -r /dev/YOUR_DEVICE -s 115200 -T 127.0.0.1
      Icom 705: rigctld -m 3085 -r /dev/YOUR_DEVICE -c 0xA4 -s 57600 -T 127.0.0.1

      Windows:
      Icom 9700: rigctld -m 3081 -r COMx -s 115200 -T 127.0.0.1
      Icom 705: rigctld -m 3085 -r COMx -c 0xA4 -s 57600 -T 127.0.0.1

    2) Check *config.ini* file and review all parameters:  
        QTH coordinates: latitude, longitude and altitude 
        
    3) Execute RigDoppler: python3 /path/to/QTrigdoppler.py

## Advanced Configuration:
    1) Support files can be modified in the *config.ini* file:
    
        [satellite]
        ;path to your TLE file
        tle_file = mykepler.txt
        tle_url = http://tle.pe0sat.nl/kepler/mykepler.txt
        ;path to AmsatNames file
        amsatnames = AmsatNames.txt
        ;path to dopler.sqf file
        sqffile = doppler.sqf
        [hamlib]
        address = localhost
        port = 4532

tle_file must contains ephemerides two line elements to calculate satellite passes over the coordinates in the [qth] section.

sqffile must contains satellites' frequencies (both downlink and uplink), following the same format as the original PCSat32 file.

amsatnames is just an auxiliary file son NORAD_ID satellites identifiers could be correlated with common satellites names used in doppler.sf file. Three columns per each satellite will list NORAD_ID identifier and common satellite name.

## Field Tests:

|     Radio     |   Satellite   |     Tester    |     Date    |
| ------------- | ------------- | ------------- | ----------- |
|  Icom 9700    |  GreenCube    |     EB1AO     |   Nov 23    |

## Feedback and bug report

Yeah, that's life .. but I want to ear from you, so send an email or a tweet and I will answer you.

