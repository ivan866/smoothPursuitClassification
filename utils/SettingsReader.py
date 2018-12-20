import os, hashlib, xml
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from tkinter import filedialog


import numpy as np

import pandas as pd


from utils import Utils



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
            self.settingsFile = file

        if self.settingsFile:
            self.dataDir = os.path.dirname(self.settingsFile)
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

        self.main.printToOut('Settings parsed ('+self.settingsFile+').', status='ok')

        if len(self.getIntervals(block='interval', ignoreEmpty=True)) == 0:
            self.main.printToOut('WARNING: No intervals specified in settings file.')





    #DATA FILTERING methods
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




    def substVersatileChannels(self, channel: str) -> str:
        """Substitutes related versatile channel names, which should be the name of the source file type channel in settings.

        :param channel: versatile channel name, like samples or gaze.
        :return: master channel name.
        """
        #FIXME hotfix
        if channel in self.main.SAMPLES_COMPONENTS_LIST and self.hasType('samples') and not self.hasType('saccade'):
            return 'samples'
        elif channel in self.main.GAZE_COMPONENTS_LIST and self.hasType('gaze') and not self.hasType('fixations'):
            return 'gaze'
        else:
            return channel




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

    def getPathAttrById(self, type:str, id:str, absolute:bool = False) -> str:
        """Returns path of a file suitable as a record tag.

        Except it still contains type and id tags.

        :param type: type str from settings.
        :param id: id str from settings.
        :param absolute: whether to concatenate with a dataDir and leave extension.
        :return: path str.
        """
        typeZeroName = self.substVersatileChannels(type)

        file = self.getTypeById(typeZeroName, id)
        path = file.get('path')

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

    def getZeroTimeById(self, type:str, id:str, parse:bool = True) -> object:
        """Resolves and returns zeroTime attribute of a file tag.

        :param type: type string from settings.
        :param id: id string from settings.
        :param parse: bool whether to parse str to timedelta or not.
        :return: zeroTime attribute in timedelta or str format, 0 or '0' if zeroTime attribute not present.
        """
        file = self.getTypeById(type, id)
        zeroTime = file.get('zeroTime', default='0')
        if len(self.getTypes(zeroTime)):
            zeroTime = self.getTypeById(zeroTime, id).get('zeroTime')
        # случай когда zeroTime ссылается на другой тип, а он отсутствует
        try:
            Utils.parseTime(zeroTime)
        except:
            self.main.reportError()
            self.main.setStatus('ERROR: Probably zeroTime attribute for type {0}, id {1} wrongly defined in settings.'.format(type, id))
            self.main.setStatus('ERROR: Consider correcting it or omit file entirely.')
            raise

        if parse:
            return Utils.parseTime(zeroTime)
        else:
            return zeroTime




    #INTERVALS
    def getIntervalById(self, id:str, block:str) -> object:
        """Returns interval with particular id attribute.
        
        :param id: id string from interval.
        :param block: which type of block to query.
        :return: ElementTree.Element
        """
        #self.main.logger.debug('get interval by id')
        return self.settings.find("{0}[@id='{1}']".format(block, id))

    def getIntervals(self, block:str, ignoreEmpty:bool=True) -> list:
        """Returns all intervals.
        
        :param block:
        :param ignoreEmpty: Whether to cut off the empty and utility intervals.
        :return: A list of interval nodes from settings.
        """
        #_ (underscore) intervals are considered special, but not empty!
        if ignoreEmpty:
            return [interval for interval in self.settings.findall(block) if interval.get('id')]
        else:
            return self.settings.findall(block)


    def getStartTimeById(self, id:str, block:str, format:bool=False) -> object:
        """Computes and returns start time of interval specified by its id.
        
        Based on start time and durations of previous intervals.
        
        :param id: id attribute of interval.
        :param block: block type (in settings).
        :param format: bool whether to convert time to str or not.
        :return: Start time of interval in timedelta object.
        """
        #self.main.logger.debug('get start time by id')
        ints = self.getIntervals(block=block, ignoreEmpty=False)
        startTime = Utils.parseTime(0)
        thisId = None
        for i in ints:
            thisId = i.get('id')
            if thisId == id:
                break
            duration = self.getDurationById(thisId, block=block)
            startTime = startTime + duration

        if format:
            return str(startTime)
        else:
            return startTime

    def getEndTimeById(self, id:str, block:str, format:bool=False) -> object:
        """Computes and returns end time of interval specified by its id.
        
        Based on start time and duration of given interval.
        
        :param id: id attribute of interval.
        :param block:
        :param format: bool whether to convert time to str or not.
        :return: End time of interval in timedelta object.
        """
        endTime = self.getStartTimeById(id, block=block) + self.getDurationById(id, block=block)
        if format:
            return str(endTime)
        else:
            return endTime


    def getDurationById(self, id:str, block:str, parse:bool=True) -> object:
        """Returns duration of interval with this id.
        
        :param id: id attribute of interval.
        :param block:
        :param parse: bool whether to parse str to timedelta or not.
        :return: Duration of interval in timedelta or str format.
        """
        dur = self.getIntervalById(id, block=block).get('duration')
        if parse:
            return Utils.parseTime(dur)
        else:
            return dur

    def getDurations(self, block:str, parse:bool=True) -> list:
        """Returns a list of durations of all intervals.
        
        :param block: from which block to gather data.
        :param parse: bool whether to parse list items to timedelta or not.
        :return: A list.
        """
        durs = []
        for interval in self.getIntervals(block=block, ignoreEmpty=True):
            durs.append(self.getDurationById(interval.get('id'), block=block, parse=parse))
        return durs

    def totalDuration(self, block:str, parse:bool=True) -> object:
        """Returns total duration of all intervals.
        
        :param block:
        :param parse: bool whether to parse str to timedelta or not.
        :return: Duration of interval in timedelta or str format.
        """
        dur = pd.DataFrame(self.getDurations(block=block, parse=True)).sum()[0]
        if parse:
            return dur
        else:
            return dur.strftime('%M:%S.%f')



    def hasType(self, type:str) -> bool:
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
        #TODO
        #bs = BeautifulSoup(self.settingsTree)
        #print(bs.prettify())

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