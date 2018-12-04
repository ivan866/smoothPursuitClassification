import os, re, math
import xml.etree.ElementTree as ET


import pandas as pd








class DataReader():

    """Helper class that reads and parses eyetracking data (currently SMI only)."""

    def __init__(self, main):
        self.main = main




    def read(self, settingsReader:object, multiData:object) -> None:
        """Actual data parsing code.
        
        Depends on pandas module.

        :param settingsReader: SettingsReader object to get xml settings tree from.
        :param multiData: MultiData object to write into.
        :return:
        """
        #self.main.logger.debug('reading data...')
        if settingsReader.check():
            settingsReader.read()
        else:
            return

        multiData.reset()
        try:
            self.readSMISamples(settingsReader, multiData)
            self.readTobiiGaze(settingsReader, multiData)
            if settingsReader.check(full=True) and multiData.check():
                self.main.printToOut('All valuable data read successfully.', status='ok')
        except:
            self.main.printError()
            raise




    #partially ported from 'readGazeContingency.R' script by ivan866, 23.11.2014
    def readSMISamples(self, settingsReader: object, multiData: object) -> None:
        """Reads SMI samples from .txt files, after IDF Converter (iTools utility package) export.

        :param settingsReader: the object created at start of the program, and populated with parsed XML settings tree.
        :param multiData: the main data structure to be populated with Pandas dataframes, one for each id/type combination.
        :return: None
        """
        for fileElem in settingsReader.genTypeFile('samples'):
            filePath = settingsReader.getPathAttrById('samples', fileElem.get('id'), absolute=True)
            fileExt = os.path.splitext(filePath)[1]
            self.main.printToOut('Reading samples ({0})...'.format(os.path.basename(filePath)))
            if fileExt.lower() == '.txt':
                self.main.printToOut('Parsing {0} file.'.format(fileExt))

                skiprows = self.determineSkiprows(filePath, '##')
                metablock = []
                with open(filePath, encoding='UTF-8') as f:
                    for n in range(skiprows+1):
                        headers = f.readline()
                        metablock.append(headers)
                metablock = ''.join(metablock)

                #tested on SMI RED-m-HP data only
                availColumns = [i for i in headers.strip().split('\t') if re.match('Time|Type|Trial|L POR X \[px\]|L POR Y \[px\]|R POR X \[px\]|R POR Y \[px\]|Timing|Latency|L Validity|R Validity|Frame|Trigger|Aux1', i)]
                multiData.setNode('availColumns', fileElem.get('id'), availColumns)

                samplesData = pd.read_table(filePath,
                                            decimal=".", sep='\t', skiprows=skiprows, header=0, usecols=availColumns, encoding='UTF-8',
                                            dtype={'Time':float, 'Type':str, 'Trial':int, 'Frame':str})
                samplesData['Time'] /= 1000000
                #first line can be MSG type, but this is OK, we count from it anyway
                zeroTime = samplesData.iloc[0]['Time']
                maxTime = samplesData.iloc[-1]['Time']
                samplesData['Time'] -= zeroTime
                samplesData = samplesData.loc[samplesData['Type']=='SMP']


                #MSG lines
                messagesData = pd.read_table(filePath,
                                             decimal=".", sep='\t', skiprows=skiprows, header=0, usecols=[0,1,2,3], encoding='UTF-8',
                                             dtype={'Time': float, 'Type': str, 'Trial': int})
                messagesData['Time'] /= 1000000
                messagesData['Time'] -= zeroTime
                messagesData = messagesData.loc[messagesData['Type'] == 'MSG']
                messagesData.rename(columns={messagesData.columns[3]: "Text"}, inplace=True)
                messagesData['Text'] = messagesData['Text'].apply(lambda x: re.sub('# Message: (.*)', '\\1', str(x)))


                #MESSAGES block
                #messages are (conventionally) assumed to have duration
                #last message duration is assumed to be up to the end of the record
                #zeroTime special interval added even if it itself equals 0
                msgNum = 0
                zeroTimeAdded  = False
                for index, row in messagesData.iterrows():
                    if not zeroTimeAdded:
                        messageTag = ET.Element('message')
                        messageTag.set('id', '_zeroTime')
                        messageTag.set('text', '')
                        duration = messagesData.iloc[0]['Time']
                        messageTag.set('duration', str(duration))
                        settingsReader.settings.append(messageTag)
                        zeroTimeAdded = True
                    msgNum = msgNum + 1
                    messageTag = ET.Element('message')
                    messageTag.set('id', str(msgNum))
                    #messageTag.set('trial', row['Trial'])
                    messageTag.set('text', row['Text'])
                    if index < len(messagesData):
                        duration = messagesData.iloc[index+1]['Time'] - row['Time']
                    else:
                        duration = maxTime - row['Time']
                    messageTag.set('duration', str(duration))
                    settingsReader.settings.append(messageTag)

                #TRIALS block
                #trials are assumed to have no gaps between them
                trialNum = 0
                zeroTimeAdded2 = False
                trialData = pd.DataFrame([messagesData.loc[index] for index,row in messagesData.iterrows() if 'FixPoint' in row['Text']])
                for index, row in trialData.iterrows():
                    if not zeroTimeAdded2:
                        trialTag = ET.Element('trial')
                        trialTag.set('id', '_zeroTime')
                        trialTag.set('text', '')
                        duration = messagesData.iloc[0]['Time']
                        trialTag.set('duration', str(duration))
                        settingsReader.settings.append(trialTag)
                        zeroTimeAdded2 = True
                    trialNum = trialNum + 1
                    trialTag = ET.Element('trial')
                    trialTag.set('id', str(trialNum))
                    trialTag.set('text', row['Text'])
                    if index < len(trialTag):
                        duration = trialTag.iloc[index + 1]['Time'] - row['Time']
                    else:
                        duration = maxTime - row['Time']
                    trialTag.set('duration', str(duration))
                    settingsReader.settings.append(trialTag)

                #TRIGGERS block (applicable for SMI HiSpeed)
                #TODO not implemented


                #get metadata
                #values assumed to be integers
                sampleRate = int(re.search('Sample Rate:\t(\d+)', metablock).groups()[0])
                screenSizePx = re.search('Calibration Area:\t(\d+)\t(\d+)', metablock).groups()
                screenWidthPx, screenHeightPx = int(screenSizePx[0]), int(screenSizePx[1])
                screenSizeMm = re.search('Stimulus Dimension \[mm\]:\t(\d+)\t(\d+)', metablock).groups()
                screenWidthMm, screenHeightMm = int(screenSizeMm[0]), int(screenSizeMm[1])
                headDistanceMm = int(re.search('Head Distance \[mm\]:\t(\d+)', metablock).groups()[0])
                #degrees, assuming the eyesight axis is centered around the screen
                screenWidthDeg = math.atan(screenWidthMm / 2 / headDistanceMm) * 180 / math.pi * 2
                screenHeightDeg = math.atan(screenHeightMm / 2 / headDistanceMm) * 180 / math.pi * 2
                screenHResMm, screenVResMm = screenWidthMm / screenWidthPx, screenHeightMm / screenHeightPx
                metadata = {'sampleRate': sampleRate,
                            'screenWidthPx': screenWidthPx, 'screenHeightPx': screenHeightPx,
                            'screenWidthMm': screenWidthMm, 'screenHeightMm': screenHeightMm,
                            'screenWidthDeg': screenWidthDeg, 'screenHeightDeg': screenHeightDeg,
                            'screenHResMm': screenHResMm, 'screenVResMm': screenVResMm,
                            'headDistanceMm': headDistanceMm}
                #experiment (record) metadata is in special property, not a separate data channel
                samplesData.metadata = metadata

            elif fileExt.lower() == '.idf':
                self.main.printToOut('ERROR: Cannot parse .idf files. Convert them to .txt first.')
                raise NotImplementedError
            elif fileExt.lower() == '.csv':
                self.main.printToOut('Parsing {0} file.'.format(fileExt))
                samplesData = pd.read_csv(filePath, sep='\t')
            else:
                self.main.printToOut('Unknown file format.')

            multiData.setNode('samples', fileElem.get('id'), samplesData)
            multiData.setNode('messages', fileElem.get('id'), messagesData)




    #TODO need determine if file format is truly Tobii .tsv, otherwise type should be 'tobii-gaze'
    #TODO Tobii API-sync package / Sync-port signal package is unknown to current implementation
    def readTobiiGaze(self, settingsReader:object, multiData:object) -> None:
        """Reads Tobii Glasses 2 gaze data from .tsv file.
        
        :param settingsReader: same as everywhere
        :param multiData: same
        :return:
        """
        for fileElem in settingsReader.genTypeFile('gaze'):
            filePath = settingsReader.getPathAttrById('gaze', fileElem.get('id'), absolute=True)
            fileExt = os.path.splitext(filePath)[1]
            self.main.printToOut('Reading gaze data ({0})...'.format(os.path.basename(filePath)))
            if fileExt.lower()=='.tsv':
                self.main.printToOut('Parsing {0} file.'.format(fileExt))
                # узнаем какие столбцы присутствуют
                headers = pd.read_table(filePath, nrows=1, encoding='UTF-16')
                availColumns = [i for i in list(headers.columns) if re.match('Recording timestamp|Gaze point|Gaze 3D position|Gaze direction|Pupil diameter|Eye movement type|Gaze event duration|Fixation point|Gyro|Accelerometer',i)]
                multiData.setNode('availColumns', fileElem.get('id'), availColumns)

                gazeData = pd.read_table(filePath, decimal=",", encoding='UTF-16', usecols=availColumns)
                # переводим в секунды
                gazeData['Recording timestamp'] /= 1000
                #gazeData['Gaze event duration'] /= 1000

                if multiData.hasAllColumns(['Gyro X','Gyro Y','Gyro Z','Accelerometer X','Accelerometer Y','Accelerometer Z'],fileElem.get('id')):
                    gazeData.drop(['Gyro X', 'Gyro Y', 'Gyro Z', 'Accelerometer X', 'Accelerometer Y', 'Accelerometer Z'], axis=1, inplace=True)

                # убираем пустые строки, которые могли образоваться после удаления строк гироскопа
                gazeData = gazeData[(gazeData['Gaze point X'].notnull()) & (gazeData['Gaze point Y'].notnull()) | \
                                    (gazeData['Eye movement type'] == 'EyesNotFound')]

                if multiData.hasColumn('Eye movement type', fileElem.get('id')):
                    gazeData.drop(['Eye movement type', 'Gaze event duration', 'Eye movement type index',
                                   'Fixation point X', 'Fixation point Y'],
                                   axis=1, inplace=True)

                #TODO translation to degrees, velocity profile

            elif fileExt.lower() == '.json':
                self.main.printToOut('ERROR: parsing .json files not implemented.')
                raise NotImplementedError
            elif fileExt.lower()=='.csv':
                self.main.printToOut('Parsing {0} file.'.format(fileExt))
                gazeData = pd.read_csv(filePath, sep='\t')
            else:
                self.main.printToOut('Unknown file format.')


            multiData.setNode('gaze', fileElem.get('id'), gazeData)




    #UTILS methods
    def determineSkiprows(self, file:str, commentStr:str) -> int:
        """

        :param file:
        :param commentStr:
        :return:
        """
        with open(file, encoding='UTF-8') as f:
            lineNum = 0
            line = f.readline()
            while line.startswith(commentStr):
                lineNum = lineNum + 1
                line = f.readline()
            return lineNum
