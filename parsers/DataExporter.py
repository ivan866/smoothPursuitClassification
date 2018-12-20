import os
from datetime import datetime
import xml.etree.ElementTree as ET



from pandas import DataFrame


from utils.SettingsReader import SettingsReader




class DataExporter():

    """Helper class that writes to files some particularly data channels useful for further data analysis."""

    def __init__(self, main):
        self.main = main
        self.settingsReader = main.settingsReader
        self.saveDir=''
        self.colsUnperceptable=['Timedelta','Record tag','Id']



    def createDir(self, prefix:str = 'OUTPUT', dryRun:bool = False) -> str:
        """Creates timestamped directory to save data into.

        :param prefix: directory name prefix.
        :param dryRun: whether to actually create the dir or just generate the path
        :return: Directory path str.
        """
        if self.settingsReader.check(full=True):
            now = datetime.now().strftime('%Y-%m-%d %H_%M_%S')
            dateTag = ET.Element('date')
            dateTag.text = now
            self.settingsReader.settings.append(dateTag)

            self.saveDir = '{0}/{1}_{2}'.format(self.settingsReader.dataDir, str(prefix), now)

            if not dryRun:
                os.makedirs(self.saveDir)
            return self.saveDir
        else:
            raise ValueError('No settings found')


    def copyMeta(self, saveDir:str = '') -> None:
        """Writes settings and report to previously created save directory.

        :param saveDir:
        :return:
        """
        if self.settingsReader.check():
            if saveDir:
                metaDir = saveDir
            else:
                metaDir = self.saveDir
            self.settingsReader.save(metaDir)
            self.main.printToOut('Current settings copied to output.')
            self.main.saveConsole(metaDir)




    def exportCSV(self, multiData:object, format:str='csv') -> None:
        """Writes all data to CSV files.

        :param multiData:
        :param format:
        :return:
        """
        if self.settingsReader.check() and multiData.check():
            self.main.printToOut('Exporting data channels to {0}.'.format(format.upper()))
            saveDir = self.createDir()
            for type in multiData.multiData.keys():
                stacked = DataFrame()
                file = '{0}/{1}_appended.{2}'.format(saveDir, type, format)
                for (channel, id) in multiData.genChannelIds(channel=type):
                    #TODO switch to tagging mode if more than 1 id in settings
                    #data = multiData.getChannelAndTag(channel, id,   block='interval', format='dataframe',   ignoreEmpty=False)
                    data = multiData.getChannelById(channel, id,   format='dataframe')
                    stacked = stacked.append(data, sort=False)

                if format == "csv" and len(stacked):
                    stacked.to_csv(file, sep='\t', header=True, index=False, mode='w')


            #----
            self.main.printToOut('Done. Data blocks tagged.', status='ok')
            self.copyMeta()