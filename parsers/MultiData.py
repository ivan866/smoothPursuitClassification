import math
from datetime import timedelta


import numpy as np
from scipy.signal import convolve
from scipy.signal import cspline1d
from scipy.signal import savgol_filter
from pandas import DataFrame


from utils.SettingsReader import SettingsReader
from utils import Utils



class MultiData():

    """Basic data structure to hold various data channels.
    
    Includes some helper methods to select different data channels and filter by timestamp.
    """

    def __init__(self, main):
        self.main = main
        self.settingsReader = main.settingsReader
        self.multiData = {}
        self.multiData['availColumns'] = {}
        self.multiData['samples'] = {}
        self.multiData['messages'] = {}
        #----
        self.multiData['fixation'] = {}
        self.multiData['saccade'] = {}
        self.multiData['pursuit'] = {}
        #----
        self.multiData['gaze'] = {}
        self.empty = True



    def genChannelIds(self, channel:str) -> tuple:
        """Generator of ids present in multiData in particular channel (i.e. 'type' tag).

        :param channel:
        :return: Tuple with current channel and id, if such id present in multiData.
        """
        if self.settingsReader.check() and self.check():
            channelZeroName = self.settingsReader.substVersatileChannels(channel)
            typeList = self.settingsReader.getTypes(channelZeroName)
            #на случай если нет комбинированного типа в настройках
            if not len(typeList):
                typeList = self.settingsReader.getTypes(channel)
            for file in typeList:
                id = file.get('id')
                if self.hasChannelById(channel, id):
                    yield (channel, id)



    def reset(self) -> None:
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
        self.empty = False





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



    def getChannelAndTag(self, channel:str, id:str, block:str, format:str='as_is', ignoreEmpty:bool=True) -> object:
        """Returns what's inside the given channel, but tags the data by record tag, id and interval first.
        
        :param channel: 
        :param id:
        :param block: which block to tag by.
        :param format: str for type conversion
        :param ignoreEmpty: Whether to cut off the empty and utility intervals.
        :return: 
        """
        chData = self.getChannelById(channel, id, format=format)
        channelZeroName = self.settingsReader.substVersatileChannels(channel)
        #zeroTime tag only applicable to INTERVALS block, because it is predefined for data channels
        if block == 'interval':
            startFrom = self.settingsReader.getZeroTimeById(channelZeroName, id)
        else:
            startFrom = 0
        pathAttr = self.settingsReader.getPathAttrById(type=channelZeroName, id=id)
        if ('Record tag' not in chData.columns) and ('Id' not in chData.columns):
            chData.insert(2, 'Record tag', pathAttr)
            chData.insert(3, 'Id', id)
        #FIXME hotfix
        elif 'Id 2' not in chData.columns:
            chData['Record tag'] = pathAttr
            chData.insert(8, 'Id 2', id)

        return self.tagIntervals(chData, startFrom, block=block, ignoreEmpty=ignoreEmpty)





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
        return data.loc[(data['Timedelta'] >= timeStart) & (data['Timedelta'] < timeEnd)]

    def getDataInterval(self, data:object, startFrom:object, interval:str, block:str) -> object:
        """Selects and returns data where timestamp is inside interval defined by its id name.
        
        :param data: data to trim from, usually after getChannelById method.
        :param startFrom: Time value to start first interval from.
        :param interval: id of interval in str format from settings.
        :param block:
        :return: Trimmed data.
        """
        if type(startFrom) is not timedelta:
            startFrom = Utils.parseTime(startFrom)

        startTime=self.settingsReader.getStartTimeById(interval, block=block) + startFrom
        endTime = self.settingsReader.getEndTimeById(interval, block=block) + startFrom
        return self.getDataBetween(data, startTime, endTime)

    def tagIntervals(self, chData:object, startFrom:object, block:str, ignoreEmpty:bool=True) -> DataFrame:
        """Tags given data by intervals, then returns a single dataframe.
        
        :param chData: data to stack intervals from, usually after getChannelById method.
        :param startFrom: zeroTime to start from.
        :param block: which type of block to tag by.
        :param ignoreEmpty: Whether to cut off the empty and utility intervals.
        :return: DataFrame object ready to group by intervals.
        """
        data = []
        ints = self.settingsReader.getIntervals(block=block, ignoreEmpty=ignoreEmpty)
        for interval in ints:
            intData = self.getDataInterval(chData, startFrom, interval.get('id'), block=block)
            intData.insert(4, block, interval.get('id'))
            intData.insert(5, '{0} duration'.format(block), interval.get('duration'))
            data.append(intData)

        #case when there is no interval block in settings at all - nothing to tag
        if len(ints)==0:
            return chData
        if len(ints)==1:
            data = data[0]
        else:
            data = data[0].append(data[1:])


        zeroBased=[]
        zeroTime = data.iloc[0, 0]
        for timestamp in data.iloc[:, 0]:
            zeroBased.append(timestamp - zeroTime)
        #FIXME should be no duplicates
        data.insert(1, 'TimestampZeroBased', zeroBased, allow_duplicates=True)

        #inheriting metadata
        try:
            data.metadata = chData.metadata
        except AttributeError:
            pass


        return data




    #EYE MOVEMENT methods
    def getVelocity(self, samplesData:DataFrame, smooth:str, convertToDeg:bool) -> DataFrame:
        """Method for calculating eye velocity, normally pixels converted to degrees first.

        :param samplesData: dataframe to operate on, containing appropriate eyetracker columns (Time, X, Y, etc.).
        :param smooth: algo to use, normally passed by command line argument.
        :param convertToDeg: whether data is passed in raw pixel values or visual angle degrees.
        :return: data with added *Velocity columns (and smoothed position columns).
        """
        #TODO data column names hard-coded, need refactor to global name dictionary mapper (SMI, Tobii variants)
        #  mapping goes to multiData metadata property
        #TODO B side (binocular) variant not implemented (applicable for SMI ETG)
        if all(samplesData['L POR X [px]'] == samplesData['R POR X [px]']) and all(samplesData['L POR Y [px]'] == samplesData['R POR Y [px]']):
            self.main.printToOut('Left and right channels detected equivalent. Working with one channel only.')
            samplesData.metadata['equivalent'] = True

        metadata = samplesData.metadata
        self.main.printToOut('WARNING: Dimensions metadata from samples file is considered correct and precise, and used in pixel-to-degree conversions.')
        self.main.printToOut('Now calculating velocity, be patient.')

        if metadata['equivalent']:
            #должен быть ведущий глаз
            sides = ['R']
        else:
            sides = ['L', 'R']

        #TODO skipping one channel if same
        for side in sides:
            for dim in ['X', 'Y']:
                # smoothing
                dataToSmooth = samplesData['{0} POR {1} [px]'.format(side, dim)]
                if smooth == 'savgol':
                    samplesData['{0}POR{1}PxSmoothed'.format(side, dim)] = savgol_filter(dataToSmooth, 15, 2)
                elif smooth == 'spline':
                    #scipy.interpolate.UnivariateSpline(x,y, k=1).get_coeffs()
                    samplesData['{0}POR{1}PxSmoothed'.format(side, dim)] = cspline1d(np.array(dataToSmooth), lamb=3)
                elif smooth == 'conv':
                    #width and shape of convolution, equivalent to moving average if all 1
                    win = np.array([1,1,1,1,1,1])
                    samplesData['{0}POR{1}PxSmoothed'.format(side, dim)] = convolve(np.array(dataToSmooth), in2=win, mode='same') / win.sum()
                else:
                    self.main.printToOut('ERROR: Invalid smoothing function specified.')



                if dim == 'X':
                    screenDim = metadata['screenWidthPx']
                    screenRes = metadata['screenHResMm']
                    multiplier = 1
                elif dim == 'Y':
                    screenDim = metadata['screenHeightPx']
                    screenRes = metadata['screenVResMm']
                    multiplier = -1


                if not convertToDeg:
                    self.main.printToOut('ERROR: Raw pixels in data are currently assumed, column names hard-coded.')
                    raise NotImplementedError
                else:
                    #converting to DEGREES
                    samplesData['{0}POR{1}Mm'.format(side, dim)]  = multiplier * (samplesData['{0} POR {1} [px]'.format(side, dim)] - screenDim / 2) * screenRes
                    coordsMm = samplesData['{0}POR{1}Mm'.format(side, dim)]
                    samplesData['{0}POR{1}Deg'.format(side, dim)] = np.sign(coordsMm) * coordsMm.apply(lambda x: Utils.getSeparation(x,0, 0,0,  z=metadata['headDistanceMm'],  mode='fromCartesian'))
                    #----
                    samplesData['{0}POR{1}MmSmoothed'.format(side, dim)] = multiplier * (samplesData['{0}POR{1}PxSmoothed'.format(side, dim)] - screenDim / 2) * screenRes
                    coordsMm = samplesData['{0}POR{1}MmSmoothed'.format(side, dim)]
                    samplesData['{0}POR{1}DegSmoothed'.format(side, dim)] = np.sign(coordsMm) * coordsMm.apply(lambda x: Utils.getSeparation(x,0, 0,0,  z=metadata['headDistanceMm'],  mode='fromCartesian'))



            #VELOCITY calculation
            x = samplesData['{0}PORXDeg'.format(side)]
            y = samplesData['{0}PORYDeg'.format(side)]
            row = DataFrame({'x1':x[1:].reset_index(drop=True), 'y1':y[1:].reset_index(drop=True),  'x0':x[:(len(x) - 1)].reset_index(drop=True), 'y0':y[:(len(y) - 1)].reset_index(drop=True)})
            seps = row.apply(lambda rowApply: Utils.getSeparation(x1=rowApply['x1'], y1=rowApply['y1'],  x2=rowApply['x0'], y2=rowApply['y0'],  z=metadata['headDistanceMm'],  mode='fromPolar'), axis=1)
            separation = np.hstack((1, seps))
            timelag = np.hstack((1, np.diff(samplesData['Time'])))
            samplesData['{0}Velocity'.format(side)] = separation / timelag

            #----
            x = samplesData['{0}PORXDegSmoothed'.format(side)]
            y = samplesData['{0}PORYDegSmoothed'.format(side)]
            row = DataFrame({'x1': x[1:].reset_index(drop=True), 'y1': y[1:].reset_index(drop=True), 'x0': x[:(len(x) - 1)].reset_index(drop=True), 'y0': y[:(len(y) - 1)].reset_index(drop=True)})
            seps = row.apply(lambda rowApply: Utils.getSeparation(x1=rowApply['x1'], y1=rowApply['y1'], x2=rowApply['x0'], y2=rowApply['y0'], z=metadata['headDistanceMm'], mode='fromPolar'), axis=1)
            separation = np.hstack((1, seps))
            timelag = np.hstack(( 1, np.diff(samplesData['Time']) ))
            samplesData['{0}VelocitySmoothed'.format(side)] = separation / timelag


        self.main.printToOut('Done.', status='ok')
        return samplesData





    #SANITY check methods
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