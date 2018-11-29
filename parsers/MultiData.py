from datetime import timedelta

from pandas import DataFrame


from SettingsReader import SettingsReader
from utils import Utils



class MultiData():

    """Basic data structure to hold various data channels.
    
    Includes some helper methods to select different data channels and filter by timestamp.
    """

    def __init__(self, main):
        self.main = main
        self.settingsReader = SettingsReader.getReader()
        self.multiData={}
        self.multiData['availColumns'] = {}
        self.multiData['samples'] = {}
        self.multiData['messages'] = {}
        self.multiData['gaze'] = {}
        self.empty = True



    def genChannelIds(self, channel:str)->tuple:
        """Generator of ids present in multiData in particular channel.

        :param channel:
        :return: Tuple with current channel and id, if such id present in multiData.
        """
        if self.settingsReader.check() and self.check():
            for file in self.settingsReader.getTypes(channel):
                id=file.get('id')
                if self.hasChannelById(channel, id):
                    yield (channel, id)




    def reset(self)->None:
        """Makes this multiData empty.
        
        :return: None.
        """
        self.__init__(self.main)

    def setNode(self, channel: str, id: str, data: object) -> None:
        """Sets chosen node in hierarchy of multiData to given data object.
        
        :param channel: string of type from settings.
        :param id: string of channel id from settings.
        :param data: object with some data, probably pandas dataframe or python list.
        :return:
        """
        #self.main.logger.debug('setting data node...')
        self.multiData[channel][id] = data
        self.empty=False



    #FILTERING methods
    def getChannelById(self, channel:str, id:str, format:str='as_is') -> object:
        """Returns what's inside multiData[channel][id] dict hierarchy, possibly converting to dataframe.
        
        :param channel: string of type from settings.
        :param id: string of channel id from settings.
        :param format: specify this str to convert to DataFrame type
        :return: data object, can be converted to dataframe.
        """
        #self.main.logger.debug('get channel by id')
        result = self.multiData[channel][id]
        if format=='dataframe':
            if type(result) == DataFrame:
                return result
            #elif type(result) == your custom data type:
            #    return yourParserFunction(self.main, result, settingsReader = self.settingsReader)
            else:
                self.main.printToOut('WARNING: Converting this type of data to DataFrame not implemented.')
                return None
        elif format=='as_is':
            return result

    def getChannelAndTag(self, channel:str, id:str, format:str='as_is', ignoreEmpty:bool=True)->object:
        """Returns what's inside the given channel, but tags the data by record tag, id and interval first.
        
        :param channel: 
        :param id:
        :param format: str for type conversion
        :param ignoreEmpty: Whether to cut off the empty and utility intervals.
        :return: 
        """
        chData = self.getChannelById(channel, id, format=format)
        startFrom = self.settingsReader.getZeroTimeById(channel, id)
        pathAttr=self.settingsReader.getPathAttrById(type=channel, id=id)
        if ('Record tag' not in chData.columns) and ('Id' not in chData.columns):
            chData.insert(2, 'Record tag', pathAttr)
            chData.insert(3, 'Id', id)
        #FIXME hotfix
        elif 'Id 2' not in chData.columns:
            chData['Record tag']=pathAttr
            chData.insert(8, 'Id 2', id)

        return self.tagIntervals(chData, startFrom, ignoreEmpty=ignoreEmpty)



    def getDataBetween(self, data:object, timeStart:object, timeEnd:object) -> object:
        """Selects and returns those data where timestamp is in given interval range.
        
        Assuming timestamp in column 0.
        
        :param data: data to trim from, usually after getChannelById method.
        :param timeStart: timestamp to begin data with in 'M:S.f' str or timedelta format.
        :param timeEnd: timestamp to end data with in 'M:S.f' str or timedelta format.
        :return: Trimmed data.
        """
        #self.main.logger.debug('get data between')
        parsedTime = Utils.parseTimeV(data.iloc[:,0])
        try:
            data.insert(1, 'Timedelta', parsedTime)
        except ValueError:
            pass

        if type(timeStart) is not timedelta:
            timeStart = Utils.parseTime(timeStart)
        if type(timeEnd) is not timedelta:
            timeEnd = Utils.parseTime(timeEnd)
        return data.loc[(data['Timedelta']>=timeStart) & (data['Timedelta']<timeEnd)]

    def getDataInterval(self, data:object, startFrom:object, interval:str) -> object:
        """Selects and returns data where timestamp is inside interval defined by its id name.
        
        :param data: data to trim from, usually after getChannelById method.
        :param startFrom: Time value to start first interval from.
        :param interval: id of interval in str format from settings.
        :return: Trimmed data.
        """
        if type(startFrom) is not timedelta:
            startFrom = Utils.parseTime(startFrom)

        startTime=self.settingsReader.getStartTimeById(interval) + startFrom
        endTime = self.settingsReader.getEndTimeById(interval) + startFrom
        return self.getDataBetween(data,startTime,endTime)

    def tagIntervals(self, chData:object, startFrom:object, ignoreEmpty:bool=True) -> DataFrame:
        """Tags given data by intervals, then returns a single dataframe.
        
        :param chData: data to stack intervals from, usually after getChannelById method.
        :param startFrom: zeroTime to start from.
        :param ignoreEmpty: Whether to cut off the empty and utility intervals.
        :return: DataFrame object ready to group by intervals.
        """
        data=[]
        ints=self.settingsReader.getIntervals(ignoreEmpty=ignoreEmpty)
        for interval in ints:
            intData=self.getDataInterval(chData, startFrom, interval.get('id'))
            intData.insert(4, 'Interval', interval.get('id'))
            intData.insert(5, 'Interval duration', interval.get('duration'))
            data.append(intData)

        #case when there is no interval block in settings at all - nothing to tag
        if len(ints)==0:
            return chData
        if len(ints)==1:
            data=data[0]
        else:
            data=data[0].append(data[1:])


        zeroBased=[]
        zeroTime=data.iloc[0,0]
        for timestamp in data.iloc[:,0]:
            zeroBased.append(timestamp-zeroTime)
        data.insert(1, 'TimestampZeroBased', zeroBased)

        return data





    def hasColumn(self, column:str, id:str) -> bool:
        """Checks if multiData contains such column in its gaze channel.
        
        :param column: Column name from Tobii gaze data.
        :param id: string of channel id from settings.
        :return: True if column present, False otherwise.
        """
        return column in self.multiData['availColumns'][id]

    def hasAllColumns(self, columns:list, id:str) -> bool:
        """Checks if multiData contains ALL these columns passed in list.
        
        :param columns: List of strings with column names.
        :param id: string of channel id from settings.
        :return: True if all columns present, False otherwise.
        """
        for col in columns:
            if col not in self.multiData['availColumns'][id]:
                return False
        return True


    def hasChannelById(self, channel:str, id:str) -> bool:
        """Checks if multiData contains this channel.id node in its hierarchy.
        
        :param channel: string of type from settings.
        :param id: string of channel id from settings.
        :return: True if such id in such channel present, False otherwise.
        """
        try:
            self.multiData[channel][id]
            return True
        except KeyError:
            return False




    def check(self) -> bool:
        """Helper method that checks if multiData present at all.
        
        :return: True if it is, False otherwise.
        """
        #self.main.logger.debug('check data')
        if not self.empty:
            return True
        else:
            self.main.printToOut('WARNING: No data loaded yet. Read data first!')
            return False