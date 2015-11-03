# Aug 26, I believe it is working now, 3:45 pm
     #  this is set up for woodgill
     # It currently has print statements everywhere and is VERY verbose
     # I am using try  --  finally  but I wanted to use try   --  else but it said synatax error

#This file does the following:
    # consumes messages from kafka topic in 
    # creates and adds data into 2 buffers 
    # the buffers are 5 seconds long staggered by 2.5 seconds
    # when a buffer is full, it processes the buffer using Wavelet Decomposition
    # sends results into kafka topic out
# Assumptions:
    # the lines of data are relatively uniform, give or take 6 characters depending on timestamp
    # up to 99 lines at end of transmission can be discarded without impacting validity of prediction
    # the transmission frequency is known to this program
    
import threading  # I am not using Threads as far as I know
import pandas as pd   # required for WD section
import pywt           # required for WD section
import time     #  for sleep
try:
    from cStringIO import StringIO     
except:
    from StringIO import StringIO
import os                             
import csv  
from pykafka import KafkaClient
from pykafka.common import OffsetType

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Choose your server and the corresponding variables  Adjust accordingly          
jupyter = "169.53.174.196"  # not enough room on server
woodgill ="159.203.3.173"
brunel = "169.53.174.201"
bluemix = "134.168.11.34"  #added August 7
bluemix2 = "129.41.253.253"  # added August 26  - For internal bluemix
bact2 = "9.26.148.85"
mainport = "9092"
SensorFrequency = 32  # Set the Hz level
speed = 1.0/SensorFrequency
windowSizeSec = 5.0
trigger = windowSizeSec/speed
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
consumer = topic1.get_simple_consumer(consumer_group="testgroup", auto_offset_reset=OffsetType.EARLIEST,  reset_offset_on_start=True, consumer_timeout_ms=5000)  #Consumer starts at start of test topic, shuts off after 5 seconds
#consumer = topic1.get_simple_consumer(consumer_group="testgroup") 
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
    # Checks if Buffer is new or contains records 
    # If new, add new message, if not, check if buffer size remains within limit 
    # Check of end of file transmission for DataSender has been reached
    # If these two condition met, add message to buffer
    # If not, Call submit data function, empty buffer and put message into empty buffer
    print("start LoadDataBuffer1") 
    Buffer.seek(0,2)
    isInUse = Buffer.tell()
    if isInUse == 0:
        Buffer.write(messageString)  # write message to bundle
    elif (counter - 1) % trigger != 0 and END == False:  #bundle size hasn't reached 160
                                                          # or whatever trigger size is.
                                                          # 1 is subtracted from counter 
                                                          # to account for the extra line
                                                          # used for the header
        Buffer.write(messageString)  # write message to bundle
        checkLastLine(Buffer, ID, HeaderBuffer, counter, END)
    else:    
        SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END)   
        Buffer.seek(0)
        Buffer.truncate(0)
        Buffer.write(messageString)  # start a new bundle
    print("End LoadDataBuffer1") 
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
    # Checks if Buffer is new or contains records 
    # If new, add new message, if not, check if buffer size remains within limit 
    # Check of end of file transmission for DataSender has been reached
    # If these two condition met, add message to buffer
    # If not, Call submit data function, empty buffer and put message into empty buffer
    print("start LoadDataBuffer2")    
    Buffer.seek(0,2)
    isInUse = Buffer.tell()    
    if isInUse == 0:
        Buffer.write(messageString)  # write message to bundle       
    elif ((counter - 1) + trigger/2) % trigger != 0 and END == False: 
                                        # Bundles doesn't start accumulating until
                                        # after 1/2 of first bundle is completed   
                                        # bundle size hasn't reached 160
                                        # or whatever trigger size is.
                                        # 1 is subtracted from counter 
                                        # to account for the extra line
                                        # used for the header        
        Buffer.write(messageString)  # write message to bundle
        checkLastLine(Buffer, ID, HeaderBuffer, counter, END)
    else:    
        SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END)  
        Buffer.seek(0)
        Buffer.truncate(0)
        Buffer.write(messageString)  # start a new bundle
    print("End LoadDataBuffer2") 
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def checkLastLine(Buffer, ID, HeaderBuffer, counter, END):
    print("Start CheckLastLine for " + ID)
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
            lineLength =  var2
            print("get length of last line, subtract that from the last position in buffer, reposition seek to that point, use tell to get value of that spot, truncate buffer to that point, effectively cutting off the shortened line")
            Buffer.seek(-lineLength, 2)            
            Buffer.truncate(Buffer.tell())       
            END = True
            print("Now we submit the shortened buffer")
            SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END)
            Buffer.seek(0)
            Buffer.truncate(0)            
            print("We have completed SubmitDataBuffer and now we truncate the buffer back to zero,  ending CheckLastLine")
    print("End CheckLastLine for " + ID)
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def SubmitDataBuffer(Buffer, ID, HeaderBuffer, counter, END):
    print("Start SubmitDataBuffer for " + ID)
    # Note:  before sending to WD, insert HeaderBuffer!
    HeaderBuffer.seek(0)
    inputBuffer = StringIO()
    inputBuffer.write(HeaderBuffer.readline())
    HeaderBuffer.seek(0)
    print("This is the HeaderBuffer: " + HeaderBuffer.readline())
    HeaderBuffer.seek(0)  # reset HeaderBuffer so it collects a new header during next round
    # if END == True :
        # HeaderBuffer.truncate(0)  # gets rid of any characters in the buffer that might exceed the next input and thus corrupt the line
    Buffer.seek(0)
                  # There seems to be one extra line that needs to be trimmed off
                  # Not sure where it originates but it interfers with WD Process
    batchCount = 0
    BufferList = Buffer.readlines()  
    batchLength = len(BufferList)
    print ("batchLength is " + str(batchLength))
    print ("We are in DataBuffer " + ID)
    if batchLength < 100 :  # this should discard any buffer less that 100 rows as
                            #  PM service will return an error for this size submission
        print ("batchLength was less that 100, so we are discarding this batch")
        Buffer.seek(0)
        Buffer.truncate(0)
        END = True  # Since the batch is at an end, END can be used to reset counter
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
    tempList = inputBuffer.readlines()
    inputBuffer.seek(0)
    
    print("This is the first line in the inputBuffer: " + tempList[0])
    
    wearables = pd.read_csv(inputBuffer)   
    dec = decompose(wearables, list('xyz'),  "ID")    
    outputBuffer = StringIO()
    outputBuffer.write(dec.to_csv())          
    contents = outputBuffer.getvalue()         
    outputBuffer.close()
    # The following is from WDThread2.py
    sendToKafka(contents)
    
    # The following was original WDProcessor.py    
    # Begin threads to be used to run producers,
    # this allows them to be shut down after a given time interval
    #if ID == ID1:
        #AA = threading.Thread(name=ID1, target=sendToKafka, args=([contents]))
        #AA.start()
        #AA.join(4) # wait for 4 seconds while blocking
        ##if AA.is_alive():
            #### Terminate
            ##AA.terminate() # This should only work with multiprocessor, not thread
            ##AA.join()        
    #else:
        #BB = threading.Thread(name=ID2, target=sendToKafka, args=([contents]))
        #BB.start()
        #BB.join(4) # wait for 4 seconds while blocking
        ##if BB.is_alive():
            #### Terminate
            ##BB.terminate()   # This should only work with multiprocessor, not thread
            ##BB.join()
    print("End SubmitDataBuffer for " + ID)          
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def sendToKafka(message):
    print("sending data to out")
    print(message)
    producer.produce([message])                         
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def wait():
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

def main():
    # August 26, 2015
    # Building a sliding window out of two buffers
    #global producer
    #global END
    #HeaderBuffer = StringIO()
    #DataToBuffer1 = StringIO()   # create StringIO for first window  
    #DataToBuffer2 = StringIO()   # create StringIO for second window
    try:
        while True:
            counter = 0 
            END = False
            HeaderBuffer = StringIO()
            DataToBuffer1 = StringIO()   # create StringIO for first window  
            DataToBuffer2 = StringIO()   # create StringIO for second window            
            try:
                time.sleep(5)
                for message in consumer:  # get message
                    if message is not None:
                        print("counter is " + str(counter))
                        if counter == 0:          
                            HeaderBuffer.seek(0,2)
                            isInUse = HeaderBuffer.tell()
                            print(str(isInUse))
                            if isInUse == 0: # If the end of HeaderBuffer  is 0 then it is empty
                                HeaderBuffer.write(str(message.value))
                                print (str(message.value))
                            else:  # If end of HeaderBuffer isn't zero, reposition at start and truncate
                                HeaderBuffer.seek(0)
                                HeaderBuffer.truncate(0)
                                print("loading into header buffer")
                                HeaderBuffer.write(str(message.value))                       
                            print(str(message.value))
                            counter += 1
                        elif counter <= int(windowSizeSec/2/speed): # 0-80 but first digit of counter is the header not part of the batch
                            print("loading into Buffer 1")
                            LoadDataBuffer1(DataToBuffer1, ID1, HeaderBuffer, str(message.value), counter, END)
                            print(str(message.value))                            
                            counter += 1  
                        elif counter > int(windowSizeSec/2/speed):  # 81 onwards
                            print("loading into both")
                            LoadDataBuffer1(DataToBuffer1, ID1, HeaderBuffer, str(message.value), counter, END)
                            LoadDataBuffer2(DataToBuffer2, ID2, HeaderBuffer, str(message.value), counter, END)
                            print(str(message.value))                                                        
                            counter += 1
                        else:  
                            print("well this is embarassing")
                print("finished looking for a message and now will do else before restarting loop")
            finally:
                wait()
                counter = 0 
                END = False
                HeaderBuffer.seek(0)
                HeaderBuffer.truncate(0)
                DataToBuffer1.seek(0)
                DataToBuffer1.truncate(0)   
                DataToBuffer2.seek(0) 
                DataToBuffer2.truncate(0)              
    finally:
        print("Have left loop in main and am closing buffers -- Good Bye")        
        HeaderBuffer.close()
        DataToBuffer1.close()   # create StringIO for first window  
        DataToBuffer2.close()   # create StringIO for second window              
            
            

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    ##++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

if __name__ == "__main__":
    main() 
    

