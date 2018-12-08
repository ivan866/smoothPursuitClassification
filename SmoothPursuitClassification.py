#!/usr/bin/env python
import argparse, sys, logging, winsound
from datetime import datetime

#py.init_notebook_mode(connected=True)




from utils.SettingsReader import SettingsReader
#from utils.Stats import Stats

from parsers.DataReader import DataReader
from parsers.DataExporter import DataExporter
from parsers.MultiData import MultiData

#from plotting.TempoPlot import TempoPlot
#from plotting.SpatialPlot import SpatialPlot
#from plotting.CombiPlot import CombiPlot






class SmoothPursuitClassification():

    """Main class of the utility.
    
    Parses command line arguments and launches calculation.
    
    """


    def __init__(self):
        self.logFormat="%(levelname)s, %(asctime)s, file %(pathname)s, line %(lineno)s, %(message)s"
        logging.basicConfig(filename='debug.log',
                            level=logging.DEBUG,
                            format=self.logFormat)
        self.logger=logging.getLogger()

        self.PROJECT_NAME = 'Smooth Pursuit Classification'
        self.PROJECT_NAME_SHORT = 'SP-c'
        self.GAZE_COMPONENTS_LIST = ['fixations','saccades','eyesNotFounds','unclassifieds',"imu","gyro","accel"]
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
    jobGroup.add_argument('--algo', type=str, choices=['ibdt', 'ivvt', 'ivdt', 'ivt', 'idt'], default='ivt', help='Algorithm name for detecting IRRELEVANT eye movement types.')
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

        for (channel, id) in spc.multiData.genChannelIds(channel='samples'):
            samplesData = spc.multiData.getChannelAndTag(channel, id, block='trial', ignoreEmpty=False)
            velocityData = spc.multiData.getVelocity(samplesData=samplesData, smooth=args.smooth, convertToDeg=True)
            spc.multiData.setNode(channel, id, velocityData)

            velocityData.loc[:, ('LVelocity', 'RVelocity')]

            #if args.algo=='ivt':
                #algo.IVTFilter(spc, spc.multiData, settingsReader=spc.settingsReader)

            #if args.classifier=='blstm':
                #nn.LSTM(spc, spc.multiData, settingsReader=spc.settingsReader)

            #if args.plots == 'xyt':
                #spc.CombiPlot(spc, spc.multiData, settingsReader=spc.settingsReader)

        spc.printToOut('Successful execution.')
        input('Press Return to exit...')
        sys.exit()
    else:
        spc.printToOut('Settings file was not specified. Unable to proceed.')
        input('Press Return to exit...')
        sys.exit()

if __name__ == "__main__":
    main()