#!/usr/bin/env python
import argparse, sys, logging, warnings, winsound
from datetime import datetime

#py.init_notebook_mode(connected=True)



from pandas import DataFrame


from utils.SettingsReader import SettingsReader

from parsers.DataReader import DataReader
from parsers.DataExporter import DataExporter
from parsers.MultiData import MultiData

from algo.IVTFilter import IVTFilter
from algo.IBDT import IBDT
from algo.IBDT import CLASSIFICATION
from algo.GazeData import MOVEMENT







class SmoothPursuitClassification():

    """Main class of the utility.
    
    Parses command line arguments and launches calculation.
    
    """


    def __init__(self):
        self.logFormat="%(levelname)s, %(asctime)s, file %(pathname)s, line %(lineno)s, %(message)s"
        logging.basicConfig(filename='debug.log',
                            level=logging.DEBUG,
                            format=self.logFormat)
        self.logger = logging.getLogger()
        warnings.filterwarnings('ignore')

        self.PROJECT_NAME = 'Smooth Pursuit Classification'
        self.PROJECT_NAME_SHORT = 'SP-c'
        self.SAMPLES_COMPONENTS_LIST = ['fixation', 'saccade', 'pursuit',    'messages']
        self.GAZE_COMPONENTS_LIST = ['fixations','saccades',    'eyesNotFounds','unclassifieds',      "imu", "gyro","accel"]
        self.VIDEO_FRAMERATE = 60


        #self.logger.debug('Instantiating classes.')
        self.settingsReader = SettingsReader(self)
        #self.stats = Stats(self)

        self.dataReader = DataReader(self)
        self.dataExporter = DataExporter(self)
        self.multiData = MultiData(self)

        #Jupyter Notebook with PLOTLY recommended instead
        #self.tempoPlot = TempoPlot(self)
        #self.spatialPlot = SpatialPlot(self)
        #self.combiPlot = CombiPlot(self)


        str1 = datetime.now().strftime('%Y-%m-%d')
        str2 = '{0} script.'.format(self.PROJECT_NAME)
        print(str1)
        print(str2)
        self.consoleContents = str1 + '\n'
        self.consoleContents += str2 + '\n'



    def printToOut(self, text:str, status:str = '') -> None:
        """Prints text to console.

        :param text: Text to print.
        :param status: status prefix to add, useful for warnings and successful operations.
        :return:
        """
        now = datetime.now().strftime('%H:%M:%S')
        if 'error' in text.lower() or 'unknown' in text.lower() or 'fail' in text.lower() or 'there is no' in text.lower() or status=='error':
            winsound.Beep(120, 400)
        elif 'warn' in text.lower() or status=='warning':
            winsound.Beep(200, 150)
        elif 'success' in text.lower() or 'complete' in text.lower() or status=='ok':
            winsound.Beep(2000, 150)
        if status:
            status='[{0}] '.format(status.upper())

        text = f'{now} {status}{text}'
        self.consoleContents += f'{text}\n'
        print(text)

    def printError(self) -> None:
        """Prints current Exception info to console.

        :return: None.
        """
        eInfo = sys.exc_info()
        text = '{0}: {1}.'.format(eInfo[0].__name__, eInfo[1])
        self.consoleContents += f'{text}\n'
        print(text)

    def saveConsole(self, saveDir:str) -> None:
        """Write current console contents to file.

        :param saveDir: Path to write into.
        :return:
        """
        reportFile = open(saveDir + '/console.txt', 'w')
        reportFile.write(self.consoleContents)
        reportFile.close()
        self.printToOut('Console contents saved to file.')




def main():
    parser = argparse.ArgumentParser(description='Launch SmoothPursuitClassification from the command line.')
    settingsFileGroup = parser.add_mutually_exclusive_group()
    settingsFileGroup.add_argument('-s', '--settings-file', type=str, help='Path to settings XML file.')

    jobGroup = parser.add_argument_group('job', 'Parameters of job running.')
    jobGroup.add_argument('--smooth', type=str, choices=['savgol', 'spline', 'conv'], default='spline', help='Filter name for gaze data smoothing.')
    jobGroup.add_argument('--algo', type=str, choices=['ibdt', 'ivvt', 'ivdt', 'ivt', 'idt'], default='ivt', help='Algorithm name for detecting IRRELEVANT (usually) eye movement types.')
    jobGroup.add_argument('--classifier', type=str, choices=['blstm', 'fasterrcnn', 'cnn', 'ssd', 'irf'], default='fasterrcnn', help='Deep-learning neural network type.')
    jobGroup.add_argument('--backend', type=str, choices=['keras', 'tf', 'neon', 'sklearn'], default='keras', help='Machine learning library to use as a backend.')
    #FIXME надо списком эти аргументы
    jobGroup.add_argument('--plots', type=str, choices=['xyt', 'xy', 'xtyt'], default='', help='Kind of plots to generate after parsing data.')


    args = parser.parse_args()
    if args.settings_file:
        spc = SmoothPursuitClassification()
        spc.printToOut('Using CLI with args: {0}.'.format(args))

        spc.settingsReader.select(args.settings_file)
        spc.dataReader.read(spc.settingsReader, spc.multiData)



        #----
        for (channel, id) in spc.multiData.genChannelIds(channel='samples'):
            #SMOOTHING
            samplesData = spc.multiData.getChannelAndTag(channel, id, block='trial', ignoreEmpty=False)
            velocityData = spc.multiData.getVelocity(samplesData=samplesData, smooth=args.smooth, convertToDeg=True)
            spc.multiData.setNode(channel, id, velocityData)




            #algo DETECTORS
            #TODO R channel hard-coded
            spc.printToOut('Classifying.')
            if args.algo == 'ivt':
                filter = IVTFilter()
                filter.runJob(velocityData[['Time', 'RVelocitySmoothed']],  150, 15, 0.250, 0.035)
                spc.printToOut( 'I-VT filter finished, with parameters: {0}'.format(filter.printParams()) )
                spc.multiData.setNode('fixation', id, filter.getResultFiltered(state='fixation'))
                spc.multiData.setNode('saccade', id, filter.getResultFiltered(state='saccade'))

            elif args.algo == 'ibdt':
                columnsData = DataFrame({'Time':velocityData['Time'] * 1000, 'confidence':1-velocityData['R Validity'], 'x':velocityData['R POR X [px]'], 'y':velocityData['R POR Y [px]']})
                filter = IBDT()
                filter.runJob(columnsData,  80, 0.5, CLASSIFICATION['TERNARY'])
                allEvents = filter.getResultFiltered()
                spc.printToOut('I-BDT classifier finished.')
                spc.multiData.setNode('fixation', id, allEvents[MOVEMENT['FIXATION']])
                spc.multiData.setNode('saccade', id, allEvents[MOVEMENT['SACCADE']])
                spc.multiData.setNode('pursuit', id, allEvents[MOVEMENT['PURSUIT']])




            #neural network CLASSIFIERS
            if args.classifier == 'blstm':
                #nn.LSTM(spc, spc.multiData, settingsReader=spc.settingsReader)
                pass
            elif args.classifier == 'fasterrcnn':
                #nn.FasterRCNN()
                pass




            #PLOTTING
            #if args.plots == 'xyt':
                #spc.CombiPlot(spc, spc.multiData, settingsReader=spc.settingsReader)






        #EXPORTING all data
        spc.dataExporter.exportCSV(spc.multiData)




        spc.printToOut('Successful execution.', status='ok')
        #input('Press Return to exit...')
        sys.exit()

    else:
        spc.printToOut('Settings file was not specified. Unable to proceed.', status='error')
        input('Press Return to exit...')
        sys.exit()

if __name__ == "__main__":
    main()