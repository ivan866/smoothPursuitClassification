import pandas as pd
from pandas import DataFrame


from eyestudio.Engine.Filter import Filter







class IVTFilter(Filter):

    """Receives angular velocity on input and outputs intervals above threshold."""
    def __init__(self):
        super().__init__()

        self.state = None
        self.last_state = None





    #INIT methods
    def printParams(self) -> str:
        """Returns a str describing the parameters set.

        :return: all parameters for this filter.
        """
        res=[]
        for k,v in self.params.items():
            res.append('{0}: {1}'.format(k,v))

        return '; '.join(res)


    def reset(self, len:int) -> None:
        """Clears result.

        :param len: data length
        :return: None
        """
        self.result = [float('nan') for i in range(len)]






    #CALCULATING methods
    def process(self, data:DataFrame, setFixation=None) -> None:
        """Main filtering routine.

        :param data: timestamp (s), angular velocity (deg/s) component
        :param setFixation: result appending handler
        :return: None
        """
        #FIXME implicitly assuming timestamps on column 0
        self.reset(data.shape[0])


        thresh = self.getParameter('min_velocity')
        minTime = self.getParameter('min_static')


        if setFixation is None:
            setFixation = self.setFixation


        #----
        fixationStart = 0
        ordinal = 0
        for index in range(data.shape[0]):
            time  = data.iloc[index, 0]
            theta = abs(data.iloc[index, 1])


            if theta < thresh:
                self.state = Filter.FIXATION

                if self.last_state != self.state:
                    ordinal = ordinal+1
                    fixationStart = index
            else:
                if self.last_state == Filter.FIXATION:
                    # Check if it's long enough
                    dur = time - data.iloc[fixationStart, 0]
                    if dur < minTime:
                        ordinal = ordinal - 1
                        # Make all into saccades again
                        for i in range(fixationStart, index):
                            setFixation(time, i, self.SACCADE, theta, ordinal)

                self.state = Filter.SACCADE

            self.last_state = self.state
            setFixation(time, index, self.state, theta, ordinal)



    def setFixation(self, time:float, index:int, state:int, theta:float, ordinal:int) -> None:
        """Result handler that appends found intervals.

        :param time: timestamp (s)
        :param index: row index
        :param state: oculomotor event code from eyestudio.Engine.Filter
        :param theta: data point actual value
        :param ordinal: state order number
        :return: None
        """
        self.result[index] = (time, state, theta, ordinal)



    def runJob(self, data:DataFrame,  min_velocity:float, noise_level:float, min_static:float, min_motion:float) -> None:
        """Sets filter parameters, processes the data and returns the filtered result.

        :param data: pandas dataframe with only 2 columns - time and speed
        :param min_velocity: min saccade velocity, otherwise consider as fixation
        :param noise_level: max noise velocity, what counts as saccade border
        :param min_static: min interval between saccades, otherwise blend into one saccade
        :param min_motion: min saccade duration, otherwise omit this saccade
        :return: None
        """
        self.setParameter('min_velocity', min_velocity)
        self.setParameter('noise_level', noise_level)
        self.setParameter('min_static', min_static)
        self.setParameter('min_motion', min_motion)

        self.process(data)





    #GROUPING methods
    def getResultFiltered(self, state:str = '') -> DataFrame:
        '''Groups result by State and Ordinal, yielding starting and ending time of events.

        :param state: which state to return
        :return: DataFrame with start/end timestamps for each ordinal or None
        '''
        #FIXME timestamp column name hard-coded
        result       = DataFrame(self.result, columns=['Time', 'State', 'Value', 'Ordinal'])
        grouped      = result.groupby(by=['State', 'Ordinal'], sort=True)
        aggregated   = grouped['Time'].agg(['count', 'min', 'max'])
        aggregated2  = grouped['Value'].agg(['mean'])
        concatenated = pd.concat((aggregated, aggregated2), axis=1)

        #motion offsets
        data  = result['Value']
        level = self.getParameter('noise_level')
        tmin  = []
        tmax  = []
        if len(concatenated.index.levels[0]) > 1:
            for index,row in concatenated.loc[1].iterrows():
                sindex = result[result['Time']==row['min']].index[0]
                eindex = result[result['Time']==row['max']].index[0]
                traversed = self.traverseOffsets(data=data, sindex=sindex, eindex=eindex, thres=level)
                tmin.append(result.iloc[traversed[0]]['Time'])
                tmax.append(result.iloc[traversed[1]]['Time'])
            #расширяем границы
            concatenated.loc[1]['min'] = tmin
            concatenated.loc[1]['max'] = tmax


        #filtering
        concatenated = self.filterValues(concatenated)
        if state=='fixation':
            return concatenated.loc[0]
        elif state=='saccade':
            if len(concatenated.index.levels[0]) > 1:
                return concatenated.loc[1]
            else:
                return DataFrame()
        elif state=='':
            return concatenated
        else:
            raise ValueError('state specified wrong.')



    def traverseOffsets(self, data, sindex:int, eindex:int, thres:float) -> tuple:
        """Runs step by step through data in given direction and finds nearest threshold value.

        :param data:
        :param sindex: start index
        :param eindex: end index
        :param thres: value to search for
        :return: found indices
        """
        myRange = data[:sindex]
        myRange = myRange[myRange <= thres]
        if len(myRange):
            svalue = myRange.index[-1]
        else:
            svalue = data.index[0]

        myRange = data[eindex:]
        myRange = myRange[myRange <= thres]
        if len(myRange):
            evalue = myRange.index[0]
        else:
            evalue = data.index[-1]

        return (svalue, evalue)





    #FILTERING methods
    def filterValues(self, values:DataFrame) -> DataFrame:
        """Filter out results based on condition.

        :param values: data to filter
        :return: filtered data
        """
        dur = []
        minMotion = self.getParameter('min_motion')
        values.apply(lambda x: dur.append(x['max'] - x['min']), axis=1)
        values['dur'] = dur
        res = values[values['dur'] >= minMotion]
        return res
