import os, hashlib, xml
import xml.etree.ElementTree as ET

from tkinter import filedialog


import numpy as np

import pandas as pd


from Utils import Utils



class SettingsReader:

    """Reads, parses and queries xml file with settings."""


    def __init__(self, main:object):
        self.main = main

        self.dataDir = None
        self.settingsFile = None
        self.settingsTree = None
        self.settings = None


    def getDir(self)->str:
        """Returns data directory containing this settings file.

        :return: file path str.
        """
        return self.dataDir




    def select(self, file:str=None) -> None:
        """Selects file with settings, specified literally by path string, opens dialog otherwise.
        
        :param file: Path string.
        :return: None
        """
        if not file:
            self.settingsFile = filedialog.askopenfilename(filetypes = (("eXtensible Markup Language","*.xml"),("all files","*.*")))
        else:
            self.settingsFile=file

        if self.settingsFile:
            self.dataDir=os.path.dirname(self.settingsFile)
            self.main.printToOut('Settings file selected.')
        else:
            self.main.printToOut('WARNING: Nothing selected. Please retry.')




    def read(self) -> None:
        """Actually reads and parses xml file contents.

        :return: 
        """
        #self.main.logger.debug('reading settings...')
        try:
            self.settingsTree = ET.parse(self.settingsFile)
            self.settings = self.settingsTree.getroot()
        except xml.etree.ElementTree.ParseError:
            self.main.printError()
            self.main.printToOut('ERROR: Bad settings file. Check your XML is valid.')
            return None
        except:
            self.main.printError()
            self.main.printToOut('ERROR: Parsing settings failed. Operation aborted.')
            return None

        self.main.printToOut('Settings parsed ('+self.settingsFile+').', color='success')

        if len(self.getIntervals(ignoreEmpty=True)) == 0:
            self.main.printToOut('WARNING: No trials specified in settings file.')





    #data filtering functions
    def genTypeFile(self, type:str) -> object:
        """Generator of ids of particular type present in settings.

        :param type:
        :return: File XML element from settings, if such file exists on disk.
        """
        found=False
        if self.check(full=True):
            for elem in self.getTypes(type):
                file= '{0}/{1}'.format(self.dataDir, elem.get('path'))
                if os.path.exists(file):
                    if not found:
                        self.main.printToOut('Reading {0} data...'.format(type))
                        found=True
                    #добавляем контрольную сумму в настройки
                    elem.set('md5', self.md5(file))
                    yield elem
                else:
                    self.main.printToOut('WARNING: File specified in settings (' + os.path.basename(file) + ') does not exist!')


    def getIds(self, id:str) -> list:
        """Queries settings for nodes with particular id attribute.
        
        :param id: id string from settings.
        :return: A list of matches with this id.
        """
        return self.settings.findall("file[@id='"+id+"']")

    def getTypes(self, type:str) -> list:
        """Returns all nodes from settings with this type attribute.
        
        :param type: type string from settings.
        :return: A list of file tags by type.
        """
        return self.settings.findall("file[@type='"+type+"']")


    def unique(self, element:str='file', field:str='') -> list:
        """Filters all specified elements by field and returns unique.
        
        :param element: On what element of settings to filter on.
        :param field: For what field to search for.
        :return: List of unique fields in these elements.
        """
        elements = self.settings.findall(element)
        l=[]
        for el in elements:
            l.append(el.get(field))
        return np.unique(l)

    def getPathAttrById(self, type:str, id:str, absolute:bool=False) -> str:
        """Returns path of a file suitable as a record tag.

        Except it still contains type and id tags.

        :param type: type str from settings.
        :param id: id str from settings.
        :param absolute: whether to concatenate with a dataDir and leave extension.
        :return: path str.
        """
        file=self.getTypeById(type, id)
        path=file.get('path')

        if absolute:
            return '{0}/{1}'.format(self.dataDir, path)
        else:
            return os.path.splitext(path)[0]

    def getTypeById(self, type:str, id:str) -> object:
        """Filters settings nodes by both type and id.
        
        :param type: type string from settings.
        :param id: id string from settings.
        :return: ElementTree.Element or list of them.
        """
        #self.main.logger.debug('get type by id')
        return self.settings.find("file[@type='" + type + "'][@id='"+id+"']")


    #INTERVALS
    def getIntervalById(self, id:str) -> object:
        """Returns interval with particular id attribute.
        
        :param id: id string from interval.
        :return: ElementTree.Element
        """
        #self.main.logger.debug('get interval by id')
        return self.settings.find("interval[@id='"+id+"']")

    def getIntervals(self, ignoreEmpty:bool=True) -> list:
        """Returns all intervals.
        
        :param ignoreEmpty: Whether to cut off the empty and utility intervals.
        :return: A list of interval nodes from settings.
        """
        #_ (underscore) intervals are considered special, but not empty!
        if ignoreEmpty:
            return [interval for interval in self.settings.findall('interval') if interval.get('id')]
        else:
            return self.settings.findall('interval')


    def getStartTimeById(self, id:str, format:bool=False) -> object:
        """Computes and returns start time of interval specified by its id.
        
        Based on start time and durations of previous intervals.
        
        :param id: id attribute of interval.
        :param format: bool whether to convert time to str or not.
        :return: Start time of interval in timedelta object.
        """
        #self.main.logger.debug('get start time by id')
        ints=self.getIntervals(ignoreEmpty=False)
        startTime=Utils.parseTime(0)
        thisId=None
        for i in ints:
            thisId = i.get('id')
            if thisId==id:
                break
            duration = self.getDurationById(thisId)
            startTime = startTime + duration

        if format:
            return str(startTime)
        else:
            return startTime

    def getEndTimeById(self, id:str, format:bool=False) -> object:
        """Computes and returns end time of interval specified by its id.
        
        Based on start time and duration of given interval.
        
        :param id: id attribute of interval.
        :param format: bool whether to convert time to str or not.
        :return: End time of interval in timedelta object.
        """
        endTime=self.getStartTimeById(id) + self.getDurationById(id)
        if format:
            return str(endTime)
        else:
            return endTime


    def getDurationById(self, id:str, parse:bool=True) -> object:
        """Returns duration of interval with this id.
        
        :param id: id attribute of interval.
        :param parse: bool whether to parse str to timedelta or not.
        :return: Duration of interval in timedelta or str format.
        """
        dur=self.getIntervalById(id).get('duration')
        if parse:
            return Utils.parseTime(dur)
        else:
            return dur

    def getDurations(self, parse:bool=True) -> list:
        """Returns a list of durations of all intervals.
        
        :param parse: bool whether to parse list items to timedelta or not.
        :return: A list.
        """
        durs = []
        for interval in self.getIntervals(ignoreEmpty=True):
            durs.append(self.getDurationById(interval.get('id'),parse))
        return durs

    def totalDuration(self, parse:bool=True)->object:
        """Returns total duration of all intervals.
        
        :param parse: bool whether to parse str to timedelta or not.
        :return: Duration of interval in timedelta or str format.
        """
        dur=pd.DataFrame(self.getDurations(True)).sum()[0]
        if parse:
            return dur
        else:
            return dur.strftime('%M:%S.%f')



    def hasType(self,type:str)->bool:
        """Checks if such file type present.

        :param type:
        :return:
        """
        if type in self.unique(field='type'):
            return True
        else:
            return False



    def check(self, full:bool=False) -> bool:
        """Returns True if settings are already selected, False otherwise.

        :param full: if to check settings actually read and parsed already.
        :return: A bool representing presence of settings file path.
        """
        #self.main.logger.debug('check settings')
        if not full:
            if self.settingsFile:
                return True
            else:
                self.main.printToOut('WARNING: Select settings first!')
                return False
        else:
            if self.settings:
                return True
            else:
                self.main.printToOut('WARNING: Read and parse settings first!')
                return False


    def save(self, saveDir:str)->None:
        """Write current settings to file.
        
        :param saveDir: Path to write into.
        :return: 
        """
        self.main.logger.debug('writing settings...')
        self.settingsTree.write(saveDir + '/' + os.path.basename(self.settingsFile))

    def md5(self, fname:str)->str:
        """Calculates and returns MD5 hash checksum of a file.

        From https://stackoverflow.com/a/3431838/2795533

        :param fname: file path.
        :return: md5 hex value.
        """
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()