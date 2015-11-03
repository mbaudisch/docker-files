# August 19, 2015
# Assumptions:
    # the lines of data are relatively uniform, give or take 6 characters depending on timestamp
    # up to 99 lines at end of transmission can be discarded without impacting validity of prediction
    # the transmission frequency is known to this program
    
    # There are three kafka topics,   test-thread,  wd-thread, prediction-thread, each will retain data for 24 hours
    # Contrary to the names, there are no threads or multiprocessors being currently used
    

#import threading
#import multiprocessing

import time     #  for sleep
try:
    from cStringIO import StringIO     
except:
    from StringIO import StringIO
import os                             
import csv  
from pykafka import KafkaClient
from pykafka.common import OffsetType
import pandas as pd   # required for WD section
import pywt           # required for WD section

# Choose your server and the corresponding variables  Adjust accordingly          

woodgill ="159.203.3.173"
brunel = "169.53.174.201"
bluemix = "134.168.11.34"  #added August 7
mainport = "9092"
SensorFrequency = 32  # Set the Hz level
speed = 1.0/SensorFrequency
windowSizeSec = 5.0
trigger = windowSizeSec/speed     # This could be simplified by multiplying SensorFrequency times windowSizeSec
trigger = int(round(trigger,0))
ID1 = "first"
ID2 = "second"


# Next is where you insert the server variable
usingHost = woodgill + ":" + mainport
usingTopic1 = "in"
usingTopic2 = "out"     

# Creates the producer and consumer 
client = KafkaClient(hosts= usingHost)
topic1 = client.topics[usingTopic1]
topic2 = client.topics[usingTopic2]
#global consumer
consumer = topic1.get_simple_consumer(consumer_group="testgroup") 
#consumer = topic1.get_simple_consumer(consumer_group="testgroup", auto_offset_reset=OffsetType.EARLIEST,  reset_offset_on_start=True, consumer_timeout_ms=5000)  
producer = topic2.get_producer()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def decomposeField(dataframe, fieldName, groupFieldName, maxCoef) :
# Wavelet Decomposition  (WD)          
    # Requires PyWavelets (http://www.pybytes.com/pywavelets/index.html) & Pandas
    # Decompose a given field using wavelet decomposition
    # dataframe:  A pandas DataFrame containing the data to decompose
    # fieldName:  The name of the field to decompose
    # groupFieldName:  Field that groups the data.  
    # Decompositions are returned for each group by row    
    coeffs = {} #Coefficients for each group
    maxLen = 0  #Largest list of coefficients

    #Grouped Case
    try:
        grouped = dataframe.groupby(groupFieldName)
        for name, group in grouped:
            #Collect coefficients for each group
            coeffs[name] = pywt.wavedec(group[fieldName], 'db1', level=2)[0].tolist()[:maxCoef]
            maxLen = max(maxLen,len(coeffs[name]))
            #Non-grouped case
    except KeyError:
        #No group.  One row of coefficients
        coeffs[0] = pywt.wavedec(dataframe[fieldName], 'db1', level=2)[0].tolist()[:maxCoef]
        maxLen = len(coeffs[0])

    # Ensures all rows of coefficients are the same length.  
    # Populates anything shorter with nan
    for coef in coeffs:
        coeffs[coef] = coeffs[coef] + [float('nan')]*(maxLen-len(coeffs[coef]))
    #Assign names of coefficients using the original field name as a prefix
    names = [fieldName + str(i) for i in range(maxLen)]    #note change from original

    #Transpose & return
    coeffD = pd.DataFrame(coeffs)
    coeffT = coeffD.T
    coeffT.columns = names
    return coeffT

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def decompose(dataframe, fieldNames, groupFieldName="",maxCoef=25):
#Provide wavelet decomposition for a list of fields in a DataFrame
    #dataframe - the pandas DataFrame containing the data to decompose
    #fieldNames -  A list of the names of fields that are to be decomposed
    #groupFieldName -  A field that defines groups within the data 
    #                  (optional--leave out if no grouping)
    #maxCoef -  The maximimum number of coefficients to retain (optional)    
    #Grouped case
    try:
        grouped = dataframe.groupby(groupFieldName)   
        #retain all fields by taking 1st row
        results = grouped.head(1)
        #index is used so merge works ok
        results.set_index([groupFieldName], inplace=True)
    except KeyError:
        results = dataframe.head(1)

    #Decompose for each field requested and merge results into a single DataFrame
    for fieldName in fieldNames:
        results = results.merge(decomposeField(dataframe, fieldName, groupFieldName, maxCoef), left_index=True, right_index=True)                       
    return results

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def LoadDataBuffer1(Buffer, ID, HeaderBuffer, messageString, counter, END):
    #global END    
    #global counter
    # Checks if Buffer is new or contains records 
    # If new, add new message, if not, check if buffer size remains within limit 
    # Check of end of file transmission for DataSender has been reached
    # If these two condition met, add message to buffer
    # If not, Call submit data function, empty buffer and put message into empty buffer

    Buffer.seek(0,2)
    isInUse = Buffer.tell()
    if isInUse == 0:
        Buffer.write(messageString)  # write message to bundle
    elif counter % trigger != 0 and END == False:  # bundle size hasn't reacher 160 or whatever trigger size is
        Buffer.write(messageString)  # write message to bundle
        checkLastLine(Buffer, ID, HeaderBuffer, counter, END)
    else:    
        SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END)    # works up to here
        Buffer.seek(0)
        Buffer.truncate(0)
        Buffer.write(messageString)  # start a new bundle

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 

def upCounter(counter, END):
    if END == True:
        counter = 0
    else:
        counter += 1
    return counter
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 

def LoadDataBuffer2(Buffer, ID, HeaderBuffer, messageString, counter, END):
    #global END
    #global counter
    # Checks if Buffer is new or contains records 
    # If new, add new message, if not, check if buffer size remains within limit 
    # Check of end of file transmission for DataSender has been reached
    # If these two condition met, add message to buffer
    # If not, Call submit data function, empty buffer and put message into empty buffer
    Buffer.seek(0,2)
    isInUse = Buffer.tell()    
    if isInUse == 0:
        Buffer.write(messageString)  # write message to bundle       
    elif (counter + trigger/2) % trigger != 0 and END == False:
        Buffer.write(messageString)  # write message to bundle
        checkLastLine(Buffer, ID, HeaderBuffer, counter, END)
    else:    
        SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END)    # works up to here
        Buffer.seek(0)
        Buffer.truncate(0)
        Buffer.write(messageString)  # start a new bundle
        
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#def bufferLength(Buffer)
    #Buffer.seek(0)
    #tempList = Buffer.readlines()
    #listLength = len(tempList)
    #Buffer.seek(0)
    #return listLength

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def checkLastLine(Buffer, ID, HeaderBuffer, counter, END):
    #global END
    #global counter
    Buffer.seek(0)
    tempList = Buffer.readlines()
    listLength = len(tempList)
    if listLength > 1:
        var1 = len(tempList[listLength-2])
        #print tempList[listLength-2]
        var2 = len(tempList[listLength-1])
        #print tempList[listLength-1]
        if var2 + 6 < var1:               # the lines in the file shouldn't vary by more that 4 digits
            Buffer.seek(0)         
            lineLength =  len(tempList[listLength - 1])  # I could use var2 for this as well
            print("get length of last line, subtract that from the last position in buffer, reposition seek to that point, use tell to get value of that spot, truncate buffer to that point, effectively cutting off the shortened line")
            Buffer.seek(-lineLength, 2)            
            Buffer.truncate(Buffer.tell())       
            END = True
            #print(Buffer.getvalue())
            print("Now we submit the shortened buffer")
            SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END)
            Buffer.seek(0)
            Buffer.truncate(0)
            #counter = 0  # reset counter to start a fresh batch/file of messages
            print("and now we truncate the buffer back to zero")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END):
    #global counter
    # Note:  before sending to WD, insert HeaderBuffer!
    HeaderBuffer.seek(0)
    inputBuffer = StringIO()
    inputBuffer.write(HeaderBuffer.readline())
    HeaderBuffer.seek(0)
    print(HeaderBuffer.readline())
    HeaderBuffer.seek(0)  # reset headerBuffer so it collects a new header during next round
    Buffer.seek(0)
                    # There seems to be one extra line that needs to be trimmed off
                    # Not sure where it originates but it interfers with WD Process
    batchCount = 0
    BufferList = Buffer.readlines()  
    batchLength = len(BufferList)
    print ("batchLength is " + str(batchLength))
    if batchLength < 100 :       # this should discard any buffer less that 100 rows as
                            # PM service will return an error for this size submission
        print ("batchLength was less that 100 so we are discarding this batch")
        Buffer.seek(0)
        Buffer.truncate(0)
        END = True
        #counter = 0  # reset counter to start a fresh batch/file of messages
        return

    Buffer.seek(0) 
    for line in Buffer.readlines():
        if batchCount == batchLength - 1:
            inputBuffer.write(line.strip('\n')) # Takes newline char off last line
        else:
            inputBuffer.write(line)
            batchCount += 1            # These previous lines get rid of the extra line
    inputBuffer.seek(0)    #repositions active point to start of buffer
    print("sending inputbuffer to decomposition now")
    wearables = pd.read_csv(inputBuffer)   
    dec = decompose(wearables, list('xyz'),  "ID")    
    outputBuffer = StringIO()
    outputBuffer.write(dec.to_csv())          
    contents = outputBuffer.getvalue()         
    outputBuffer.close()
    # *******************************************
    sendToKafka(contents)
          
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 


def sendToKafka(message):
    print("sending data to wd-thread")
    print(message)
    producer.produce([message])  


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++



def main():

    while True:
        counter = 0 
        END = False
        HeaderBuffer = StringIO()
        DataToBuffer1 = StringIO()   # create StringIO for first window  
        DataToBuffer2 = StringIO()   # create StringIO for second window         
        try: 
            time.sleep(10)
            print("try  for message in consumer") 
            for message in consumer:  # get message
                print("before the messages are checked")
                if message is not None:
                    print("counter is " + str(counter))
                    if counter == 0:
                        print("loading into header buffer")
                        HeaderBuffer.write(str(message.value))
                        print(str(message.value)) 
                        counter += 1
                    elif counter < int(windowSizeSec/2/speed):
                        print("loading into Buffer 1")                
                        LoadDataBuffer1(DataToBuffer1, ID1, HeaderBuffer, str(message.value), counter, END)
                        #counter += 1 
                        counter = upCounter(counter, END)                       
                        print(str(message.value))                
                    elif counter >= int(windowSizeSec/2/speed):
                        print("would print into both buffers now: ")    
                        print(str(message.value))
                        LoadDataBuffer1(DataToBuffer1, ID1, HeaderBuffer, str(message.value), counter, END)
                        LoadDataBuffer2(DataToBuffer2, ID2, HeaderBuffer, str(message.value), counter, END)
                        #counter += 1
                        counter = upCounter(counter, END)
                else:  
                    print("well this is embarassing")
            print("finished for message in consumer   will wait for time?")
        finally:
            #counter = 0
            #print('I will now wait 5 minutes for wearable sensor transmission ')
            #time.sleep(60)
            #print('I will now wait 4 minutes for wearable sensor transmission ')
            #time.sleep(60)
            #print('I will now wait 3 minutes for wearable sensor transmission ')
            #time.sleep(60)
            #print('I will now wait 2 minutes for wearable sensor transmission ')
            #time.sleep(60)
            print('I will now wait 1 minute for wearable sensor transmission ')
            time.sleep(60)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 
if __name__ == "__main__":
    main()

