from PyQt4 import  QtGui
from PyQt4 import  QtCore

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
import json
import matplotlib.pyplot as plt
import numpy as np
import time
import datetime
class histpanel(QtGui.QWidget):
    def __init__(self,app):
        super(histpanel,self).__init__()
        self.layout =QtGui.QVBoxLayout()
        self.setLayout(self.layout )
        self.figure=plt.figure()
        self.canvas=FigureCanvas(self.figure)
   
        self.layout.addWidget(self.canvas)
        self.histdata=None
        self.app=app
    def plot(self,datastr):
        data=json.loads(unicode(datastr))
        self.histdata=np.array(data["data"]["history"])
        self.timestep(datastr)
         
    def timestep(self,resultstr):
        data=json.loads(unicode(resultstr))
        timestamp=data["data"]["stat"]["time"]
     
        if ((self.histdata is not None) and 
            self.app.tab.currentIndex()==2 ):
            self.figure.clf()
            ax=self.figure.add_subplot(111)
            ax.hist(self.histdata-np.ceil(timestamp),bins=100,range=(-100,0))
            ax.set_xlim((-100,0))
            tstr= datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            ax.set_title(tstr)
            self.canvas.draw()
          