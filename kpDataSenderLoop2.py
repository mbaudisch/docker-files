# August 19, 2015   Currently set for woodgill

import time
import csv
#from pykafka import KafkaClient    # This one doesn't have a asynchronous producer yet
from kafka import SimpleProducer, KafkaClient
import os
from time import sleep
import os.path     # used to check if file exists

# usingDataFile  (now test9319.csv)  (data file) must be in same directory as script

# Choose your server and the corresponding variables           

woodgill ="104.236.104.119"

bluemix = "134.168.11.34"
bluemix2 = "129.41.253.253"

mainport = "9092"
SensorFrequency = 32  # Set the Hz level
speed = 1.0/SensorFrequency  
minPacketLength = 250.0   #20 seconds
workingdir = os.getcwd()
#usingDataFile = "act9319-34.csv"     #file:///startfile/test.csv
usingDataFile = "test9319-2.csv"     #file:///startfile/test.csv
FileThere = True 
# Insert the server variable
#usingHost = bluemix + ":" + mainport
usingHost = woodgill + ":" + mainport
#topic = "test-thread" 
topic = "cluster"
# Using kafka-python  at http://kafka-python.readthedocs.org/en/latest/usage.html#simpleproducer
client = KafkaClient(hosts= usingHost)
kafka = KafkaClient(usingHost)
# To send messages asynchronously
producer = SimpleProducer(kafka, async=True)
# To send messages synchronously, use the following. 
#    Synchronous messages run approx 8 per second
#    Asynchronous messages run approx 40,000 per second (maybe I exagerate (mayeb not))
#producer = SimpleProducer(kafka, async=False,req_acks=SimpleProducer.ACK_AFTER_LOCAL_WRITE,ack_timeout=2000,sync_fail_on_error=False)

# This is how you use this producer to send messages
#producer.send_messages(b'my-topic', b'async message')
# This is how you do it using variables
#producer.send_messages(topic, message)

# To wait for acknowledgements
# ACK_AFTER_LOCAL_WRITE : server will wait till the data is written to
#                         a local log before sending response
# ACK_AFTER_CLUSTER_COMMIT : server will block until the message is committed
#                            by all in sync replicas before sending a response
#producer = SimpleProducer(kafka, async=False,
                          #req_acks=SimpleProducer.ACK_AFTER_LOCAL_WRITE,
                          #ack_timeout=2000,
                          #sync_fail_on_error=False)

#responses = producer.send_messages(b'my-topic', b'another message')
#for r in responses:
    #logging.info(r.offset)

# To send messages in batch. You can use any of the available
# producers for doing this. The following producer will collect
# messages in batch and send them to Kafka after 20 messages are
# collected or every 60 seconds
# Notes:
# * If the producer dies before the messages are sent, there will be losses
# * Call producer.stop() to send the messages and cleanup
#producer = SimpleProducer(kafka, async=True,
                          #batch_send_every_n=20,
                          #batch_send_every_t=60)




def main():
    while True: 
        # ++++++++++++++++==========+++++++++++
        ## This section gets a test file to send 
        ## It could be adapted to read a series of files in succession
        # ++++++++++++++++==========+++++++++++
        filenames = next(os.walk(workingdir))[2]  #gets list of all file names from directory
                                                #in which the script is running -- 
                                                #so data file must be in there
        for file in filenames:
            if file == usingDataFile:
                FileThere = True
                break
            else:
                FileThere = False
        # ++++++++++++++++==========+++++++++++         
        x = 0    #counts number of lines in transmission
        repeat = False   #Used to decide if file needs to be resent due to shortness 
        Xline = ""
        if FileThere: # this line would change if we were reading many files in succession

            #while x <= int(minPacketLength/speed): # we need at least 640 messages to get a 20 second window, 
            while True :                           # so, if going through the file once still hasn't given 
                                                   # us enough messages, the loop will run again 
                                                   # (and again) until enough messages have been sent
                with open(usingDataFile) as file: 
                    for line in file:
                        if repeat == True: # we trim the top line off because it is a header line
                            print(line)   # This skips the header line but seems to leave in a blank line
                            repeat = False
                        else : 
                            producer.send_messages(topic, line)
                            print(line +  '   ' + str(x))               
                            x += 1
                            sleep(0.03125)  #speed of Accelerometer is 32Hz so gap between message is 0.03125 ms
                print("Closing file " + str(x) + " \n" )   
                #if x <= int(minPacketLength/speed):    # at 32 Hz, 640 records == 20 seconds which we need for a good reading from WD & PM
                repeat = True
                print("expecting to repeat")

            #producer.send_messages(topic, "stop")    # This is added at end of transmission
                                          # will be trimmed off by WDProcessor 
                                          # but used to mark end of transmission
            #if os.path.isfile(usingDataFile):       
             #   os.rename(usingDataFile, usingDataFile + "-sent")    
        else:
            #print('I will now wait 5 minutes for a new test.csv ')
            #time.sleep(60)
            #print('I will now wait 4 minutes for a new test.csv ')
            #time.sleep(60)
            #print('I will now wait 3 minutes for a new test.csv ')
            #time.sleep(60)
            #print('I will now wait 2 minutes for a new test.csv ')
            #time.sleep(60)
            print('I will now wait 1 minute for a new test.csv ')
            time.sleep(60)



if __name__== '__main__':
    main()

