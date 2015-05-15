import time
import RPi.GPIO as GPIO
import math
import time
from datetime import datetime
import picamera 
import logging
from ctypes import *
from threading import Thread
from Queue import Queue
#cdll.LoadLibrary("./bcm2835.so")

GPIO.setmode(GPIO.BOARD)
GPIO.setup(40,GPIO.OUT) # red led
GPIO.setup(38,GPIO.IN, pull_up_down=GPIO.PUD_UP) # button
GPIO.setup(37,GPIO.OUT) # green led
GPIO.setwarnings(False)
sensor = CDLL("/home/pi/rpi_sensor_board/sensor.so")
cam = picamera.PiCamera()
#cam.resolution = (1024, 768)
#pi camera config settings
cam.resolution = (2592,1944)
cam.exposure_mode = 'antishake'
cam.awb_mode = 'cloudy'
tmstmp = time.strftime("%Y%m%d-%H%M%S")
#keep log of flight
logging.basicConfig(format='%(asctime)s %(message)s',filename='kite'+str(tmstmp)
+'.log',level=logging.DEBUG)
  
#class for mpl3115a2 - copied from example code for Xtrinsic board
class mpl3115a2:
	def __init__(self):
		if (0 == sensor.bcm2835_init()):
			print "bcm3835 driver init failed."
			logging.debug("bcm3835 driver init failed")
			return
			
	def writeRegister(self, register, value):
	    sensor.MPL3115A2_WRITE_REGISTER(register, value)
	    
	def readRegister(self, register):
		return sensor.MPL3115A2_READ_REGISTER(register)

	def active(self):
		sensor.MPL3115A2_Active()

	def standby(self):
		sensor.MPL3115A2_Standby()

	def initAlt(self):
		sensor.MPL3115A2_Init_Alt()

	def initBar(self):
		sensor.MPL3115A2_Init_Bar()

	def readAlt(self):
		return sensor.MPL3115A2_Read_Alt()

	def readTemp(self):
		return sensor.MPL3115A2_Read_Temp()

	def setOSR(self, osr):
		sensor.MPL3115A2_SetOSR(osr);

	def setStepTime(self, step):
		sensor.MPL3115A2_SetStepTime(step)

	def getTemp(self):
		t = self.readTemp()
		t_m = (t >> 8) & 0xff;
		t_l = t & 0xff;

		if (t_l > 99):
			t_l = t_l / 1000.0
		else:
			t_l = t_l / 100.0
		return (t_m + t_l)

	def getAlt(self):
		alt = self.readAlt()
		alt_m = alt >> 8 
		alt_l = alt & 0xff
		
		if (alt_l > 99):
			alt_l = alt_l / 1000.0
		else:
			alt_l = alt_l / 100.0
			
		return self.twosToInt(alt_m, 16) + alt_l
	def getBar(self):
		alt = self.readAlt()
		alt_m = alt >> 6 
		alt_l = alt & 0x03
		
		if (alt_l > 99):
			alt_l = alt_l 
		else:
			alt_l = alt_l 

		return (self.twosToInt(alt_m, 18))

	def twosToInt(self, val, len):
		# Convert twos compliment to integer
		if(val & (1 << len - 1)):
			val = val - (1<<len)

		return val

#class for mma8491q - copied from example code for Xtrinsic board	
class MMA8491Q_DATA(Structure):
	_fields_  = [("Xout", c_int16),
	("Yout", c_int16),
	("Zout", c_int16)]

class mma8491q:
	def __init__(self):
		if (0 == sensor.bcm2835_init()):
			print "bcm3835 driver init failed."
			logging.debug("bcm3835 driver init failed.")
			return	

	def init(self):
		sensor.MMA8491Q_Init()
		
	def enable(self):
		sensor.MMA8491Q_Enable()

	def disEnable(self):
		sensor.MMA8491Q_DisEnable()
		
	def writeRegister(self, register, value):
		sensor.MMA8491Q_WRITE_REGISTER()

	def readRegister(self, register):
		return sensor.MMA8491Q_READ_REGISTER()

	def read(self, data):
		sensor.MMA8491_Read(data)	

	def getAccelerometer(self):
		data = 	MMA8491Q_DATA()
		pdata = pointer(data)
		self.read(pdata)
		return (data.Xout, data.Yout, data.Zout);
		
	def __str__(self):
		ret_str = ""
		(x, y, z) = self.getAccelerometer()
		ret_str += "X: "+str(x) + "  "
		ret_str += "Y: "+str(y) + "  "
		ret_str += "Z: "+str(z)
		
		return ret_str
		
	def twosToInt(self, val, len):
		# Convert twos compliment to integer
		if(val & (1 << len - 1)):
			val = val - (1<<len)

		return val

# use accelerometer to see when camera is pointing down
def leveltest(x,y,z):
	if int(x) > -300 and int(x) < 3000 and int(y) > -300 and int(y) < 300:
		return (True)
	else:
		return (False)		

# wait for the camera to be pointing down
def waitForLevel():
	waiting = True
	while waiting:
		(x, y, z) = mma.getAccelerometer()
		if leveltest(x,y,z):
			waiting = False
		time.sleep(0.5)
		mma.enable()
	return 

# turn the led red
def led_red(state):
	if state == 'on':
		GPIO.output(37,GPIO.LOW)
		GPIO.output(40,GPIO.HIGH)
	elif state == 'off':
		GPIO.output(40,GPIO.LOW)
	else:
		print 'error'
	return

# turn the led green
def led_green(state):
	if state == 'on':
		GPIO.output(40,GPIO.LOW)
		GPIO.output(37,GPIO.HIGH)
	elif state == 'off':
		GPIO.output(37,GPIO.LOW)
	else:
		print 'error'
	return

#wait for the button to be pressed

def butwatch(out_q):

    logging.info('Initialising')
    state = 'waiting'
    while True:
#               print GPIO.input(38)
        if GPIO.input(38) == 0 and state != 'pressed':
	    logging.info('Starting capture run')
	    print 'button pressed'
            state = 'pressed'
            out_q.put('pressed')
            time.sleep(0.5)
            state = 'waiting'

#initialise sensors
mma = mma8491q()
mma.init()
mma.enable()
mpl = mpl3115a2()
mpl.initAlt()
mpl.active()


q = Queue()
t1 = Thread(target=butwatch, args=(q,))
t1.start()
led_red('on')
while True:
	#print 'reading q1'
	#logging.info('+ filename + ' at ' + str(mpl.getAlt()))
	data = q.get()
	if data == 'pressed':
		led_red('off')
		time.sleep(0.2)
		led_green('on')
		#cam.start_preview()
		data = None

		for filename in cam.capture_continuous('img{timestamp:%Y-%m-%d-%H-%M-%S}.jpg'):
			waitForLevel()
			print 'snap ' + str(mpl.getAlt())
			logging.info('Captured ' + filename + ' at ' + str(mpl.getAlt()))
			time.sleep(2)
			if q.empty():
				print 'empty'
			else:	
				print 'not empty'
				data = q.get()
				if data == 'pressed':
					print 'off'
					led_green('off')
					time.sleep(0.2)
					led_red('on')
					break



    		

GPIO.cleanup()
