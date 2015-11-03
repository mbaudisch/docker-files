# August 14, 2015   -- set for woodgill
 

#This file does the following:
    # Consumes out from wd
    # Formats the results of WD processing
    # POSTs results to Predictive Modelling Service and gets response
    # Sends response to Kafka under topic "Predictions"

import time     #  for sleep
from flask import Flask, jsonify, json      # required for testing various sections
from flask import request                   # required for POST method          
from flask import Response                  # required to tidy up the GET method
try:
    from cStringIO import StringIO      # required for POST method 
except:
    from StringIO import StringIO
import os                              # required for trim_file to delete temp file
import requests                        # use to make POST request of PM Service
import json  #  don't think I need this
import csv  
from pykafka import KafkaClient
from pykafka.common import OffsetType
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Choose your server and the corresponding variables  Adjust accordingly          
jupyter = "169.53.174.196"
woodgill ="159.203.2.173"
brunel = "169.53.174.201"
bluemix = "134.168.11.34"  #added August 7
bact2 = "9.26.148.85"
mainport = "9092"
# The first of the following was the access we started with- it apparently became unusable around August 10th or that was when I noticed that connections were refused
#PMurl = 'https://ibmpmsrvus1.pmservice.ibmcloud.com:8443/pm/v1/score/WearablesHMPPrediction?accesskey=DvSePki8tpPNFyw42uooEbUJmDYybQ4H3ii57PvSLF2AwAsf2N08DImQF+LovNsq8Fnkmd5EGZl1HcKFvamM3D/qaM54E4Gva4kPB59QU99ExR6HFoUEzt9N2wFd8lfZ0E/S+bkATCu6VXEYVuznVg=='
# Access keey for predictive modelling service in External
#PMurl = 'https://ibmpmsrvus1.pmservice.ibmcloud.com:8443/pm/v1/score/WearablesHMPPrediction?accesskey=F8nlxurUn8/nfFcIUtMHc9JoU3ip4NHtgXJOVmt8omFWZ1RzfqGpLdKay8Eq7MDL+Y/a/Ea77GKJN7iYV2/2nH51U75ZN2CQ8v6A37yD3faomAOzx3iV9xFT6aMdr2fWyXdvnosLitHr+/akap+g1S2P7EX0tz7zwxsGvlW8+3g='
# Access for Predictive Modelling service in Haifa
PMurl = 'https://ibmpmsrvus1.pmservice.ibmcloud.com:8443/pm/v1/score/WearablesHMPPrediction?accesskey=gDhYcpQ+zOaY/DLvV8P3L0K369PlP5wtqn4um15dn4o51KDkgjXlsiLAd8KhigvUfOTh1mk1XvO3lKuQ1gPlUxjGNOcn/tWNU7nFAPaNmR7rvOw8D9EXyya/cnsPOg+0nbS5ULnuH1U8qobfyGQMtw=='

PMTableName = 'wearablesDecomposed'

# Next is where you insert the server variable
usingHost = woodgill + ":" + mainport
usingTopic1 = "out"
usingTopic2 = "done"     

# Creates the producer and consumer 
client = KafkaClient(hosts= usingHost)
topic1 = client.topics[usingTopic1]
topic2 = client.topics[usingTopic2]
#consumer = topic1.get_simple_consumer(consumer_timeout_ms=5000)
consumer = topic1.get_simple_consumer(consumer_group="testgroup")
producer = topic2.get_producer()


#consumer = topic1.get_simple_consumer(consumer_group="testgroup", auto_offset_reset=OffsetType.EARLIEST, reset_offset_on_start=True,consumer_timeout_ms=5000)
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
   
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#POST to Predictive Modelling Service
def PostToPM():
    url = PMurl
    f = open(transitFile, 'rb')
    payload = f.read()    
    headers = {'Content-Type':'application/json'}
    r = requests.post(url, headers=headers, data=payload)
    return r.text
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#POST to Predictive Modelling Service using StringIO buffer
def PostToPM_Buffer(data):
    url = PMurl
    payload = data   
    headers = {'Content-Type':'application/json'}
    r = requests.post(url, headers=headers, data=payload)
    return r.text
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def CreateInstance(Buffer, tablename):
    #create the dict to format appropriate for PM Service
    instance2 = {'tablename':tablename}
    instance2['header'] = ['r1c1','r2c1']
    instance2['data'] = []   
    j = 0
    Buffer.seek(0)  
    for line in Buffer.readlines():
        if j == 0: 
            line = line.rstrip('\n')
            line = line.split(',')
            instance2['header'] = line # might have to take the tailing newline character off see: https://docs.python.org/2/library/stdtypes.html#bltin-file-objects            
            j += 1
        else:
            line = line.rstrip('\n')
            line = line.split(',')
            instance2['data'].append(line) # see note above                 j += 1
    return instance2
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def main():

    PMInBuffer = StringIO()
    while True:
        try:
            time.sleep(10)
            for message in consumer:  # get message
                if message is not None:     
                    # f.write(str(message.value))  # write message to bundle
                    PMInBuffer.write(str(message.value))
                    print(PMInBuffer.getvalue())
                    PMBack = PostToPM_Buffer(json.dumps(CreateInstance(PMInBuffer, PMTableName)))
                    producer.produce ([PMBack])   #sends PM results to Kafka server under prediction topic
                    PMInBuffer.seek(0)                    
                    PMInBuffer.truncate(0)
                else:
                    print("jump up and down")
                    
        finally:
            #print ("I will shut my eyes for 5 minutes")
            #time.sleep(60)  # 300 = 5 minutes 
            #print ("I will shut my eyes for 4 minutes")
            #time.sleep(60)  # 300 = 5 minutes               
            #print ("I will shut my eyes for 3 minutes")
            #time.sleep(60)  # 300 = 5 minutes   
            #print ("I will shut my eyes for 2 minutes")
            #time.sleep(60)  # 300 = 5 minutes           
            print ("I will shut my eyes for 1 minute")
            time.sleep(60)  # 300 = 5 minutes
            
            
if __name__ == "__main__":
    main()        
        
