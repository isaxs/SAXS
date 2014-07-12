import sys
import zmq
from multiprocessing import Process
import time,json
import os
import SAXS
from jsonschema import validate,ValidationError
import base64
import traceback
from optparse import OptionParser
import hashlib
class AuthenticationError(Exception):
     def __init__(self, value):
         self.message = value
         self.value=value
     def __str__(self):
        return repr(self.message)

def subscribeToFileChanges(queue,url,dir):
    port = "5556"
 
    # Socket to talk to server
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    print "Feeder at: ",url
    socket.connect ( url)
    socket.setsockopt(zmq.SUBSCRIBE,"")
    while True:
       
        string = socket.recv()
        obj=json.loads(string)
        file= os.path.normpath(obj['argument'])
        if file.startswith( os.path.normpath(dir)):
            if file.endswith('.tif'):
                queue.put(obj['argument'])
        



class Server():
    """
    class to manage a saxsdog server
    """
    def __init__(self,conf):
        self.files=None
        context = zmq.Context()
        self.comandosocket = context.socket(zmq.REP)
        
        parser = OptionParser()
        usage = "usage: %prog [options]"
        parser = OptionParser(usage)
        parser.add_option("-p", "--port", dest="port",
                      help="Port to offer command service. Default is 7777.", metavar="port",default="") 
        
        parser.add_option("-t", "--threads",type="int", dest="threads",
                      help="Number of concurrent processes.",default=1)
        parser.add_option('-f','--feeder',dest="feederurl",metavar="tcp://hostname:port",default="",
                          help="Specify the URL of the new file event service (Saxsdog Feeder)"
                          )
        
        parser.add_option("-w", "--watch", dest="watchdir", default=False,action="store_true",
                      help="Watch directory for changes, using file system events recursively for all sub directories.")
      
        
        parser.add_option("-o", "--out", dest="outdir", default="out",
                      help="Specify output directory. Default is './out'.")
        parser.add_option("-i", "--inplace", dest="inplace", default=False,action="store_true",
                      help="Files are written, in place, in the directory of the image.")
   
        (self.options, self.args) = parser.parse_args(args=None, values=None)
        if self.options.feederurl=="":
            self.feederurl=conf["Feeder"]
        if self.options.port=="":
            serverport=conf['Server'].split(':')[-1]
        self.secret=conf['Secret']
        print "server listenes at tcp://*:%s" % serverport
        self.comandosocket.bind("tcp://*:%s" % serverport)
        self.commandschema=json.load(open(os.path.dirname(__file__)+'/LeashRequestSchema.json'))
        self.imagequeue=None
        self.feederproc=None
           
           
    def start(self):
        while True:
            try:
                message=self.comandosocket.recv_multipart()
                 
                object=json.loads(message[0])
                validate(object,self.commandschema)
                self.authenticate(object)
                attachment=message[1:]
                result=self.commandhandler(object,attachment)
            except ValidationError as e:
                result={"result":"ValidationError in request","data":e.message}
            except ValueError as e:
                result={"result":"ValueError in request","data":{"Error":e.message}}
            except  AuthenticationError as e:
                 result={"result":"AuthenticationError in request","data":{"Error":e.message}}
            self.comandosocket.send(json.dumps(result))
            
    def authenticate(self,data):
        sign=data['sign']
        data["sign"]=""
        m=hashlib.sha512()
        now=time.time() 
        print json.dumps(data)
        m.update(json.dumps(data, sort_keys=True))
        m.update(self.secret)
        if not abs(data["time"]-now)<900:
            raise AuthenticationError("Untimely request.")
        if not sign==m.hexdigest():
            raise AuthenticationError("Wrong signature.")
        
                
            
    
    def commandhandler(self,object,attachment):
         command=object['command']
         if command=='new':
            result= self.start_image_queue(object,attachment)
            
         elif command=='abort':
             result=self.queue_abort()
         elif command=='close':
             result=self.queue_close()
         elif command=="readdir":
             result=self.readdir(object)
         elif command=="plot":
             result=self.plot()
         elif command=="stat":
             result={"result":"stat","data":{"stat":self.stat()}}
         else:
             result={"result":"ErrorNotimplemented"}
         print command   
         
         return result
    def start_image_queue(self,object,attachment):
        self.lasttime=time.time()
        self.lastcount=0
        self.queue_abort()
        try:
            o=SAXS.AttrDict({"plotwindow":False,"threads":self.options.threads,"watch":True,"watchdir":self.options.watchdir,"walkdirinthreads":False,
                             "silent":False,"plotwindow":False,"outdir":self.options.outdir,"inplace":self.options.inplace,"writesvg":False,
                             "writepng":False,"resume":False
                             })
            maskobj=json.loads(attachment[0])
            mskfilename=os.path.join(object['argument']['directory'],
                                     "saxsdogserver"+os.path.basename(maskobj['filename']))
            print mskfilename
            mskfile=open(mskfilename,'wb')
            mskfile.write(base64.b64decode(maskobj['data']))
            mskfile.close()
            object['argument']['calibration']['MaskFile']=mskfilename
            cal=SAXS.calibration(object['argument']['calibration'])
            self.imagequeue=SAXS.imagequeue(cal,
                    o,[object['argument']['directory']])
            self.imagequeueprocess=Process(target=self.imagequeue.start)
            self.imagequeueprocess.start()
            self.feederproc=Process(target=subscribeToFileChanges,args=(self.imagequeue.picturequeue,self.feederurl,object['argument']['directory']))
            self.feederproc.start()
            self.lasttime=time.time()
            self.lastcount=0
            result={"result":"queue initiated ","data":{"cal":object['argument']['calibration']}}
        except IOError as (e,v,t): 
            result={"result":"IOError","data":{"Error": e.message}}
        except ValueError as e:
            result={"result":"ValueError","data":{"Error": e.message}}
        return result
    def queue_abort(self):
        if self.imagequeue:
            self.imagequeue.stop()
            self.imagequeueprocess.terminate()
            self.imagequeueprocess.join(1)
        self.queue_close()
        return {"result":"queue aborted","data":{"stat":self.stat()}}
    def queue_close(self):
        if self.feederproc:
            self.feederproc.terminate()
            self.feederproc.join(0)
        return {"result":"queue closed","data":{"stat":self.stat()}}
    def readdir(self,object):
        try:
            self.imagequeue.fillqueuewithexistingfiles()
        except AttributeError as msg:
            result={"result":"ValueError","data":{"Error":"Start Queue first"}}
            return result
        return {"result":"queue restarted with all files","data":{"stat":self.stat()}}
    def plot(self):
        picture=self.imagequeue.picturequeue.get(timeout=5)
        (file,data)=self.imagequeue.procimage(picture,0)
        result={"result":"plot","data":{"filename":file,"array":data.tolist(),"stat":self.stat()}}
        return result
    def stat(self):
        if self.imagequeue:
            timep=time.time()-self.lasttime
            self.lasttime=time.time()
            newpic=self.imagequeue.allp.value-self.lastcount
            self.lastcount=self.imagequeue.allp.value
            return {"images processed":self.imagequeue.allp.value,
             "queue length":self.imagequeue.picturequeue.qsize(),
             "time interval":timep,
             "pics":newpic,
             
             }
        else:
            return{}
def saxsdogserver():
     serverconf=json.load(open(os.path.expanduser("~"+os.sep+".saxdognetwork")))
     validate(serverconf,json.load(open(os.path.dirname(__file__)+os.sep+'NetworkSchema.json')))
     S=Server(serverconf)
     S.start()
if __name__ == '__main__':
     saxsdogserver()
    