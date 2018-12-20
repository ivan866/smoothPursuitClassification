#TODO try angular speed mode
from collections import deque



import numpy as np
from pandas import DataFrame


import cv2



from algo.GazeData import GazeDataEntry
from algo.GazeData import MOVEMENT








CLASSIFICATION = {'TERNARY':0,
                  'BINARY':1
                  }



class IBDT():
    """Main class of the algorithm
    Contains methods for training and data manipulation.

    Confidence column is not meaningful for SMI eyetrackers. Replaced by 1-validity.

    Based on Santini, Fuhl, Kubler, Kasneci, University of Tubingen, 2016, 2017.
    Ported by ivan866 on 2018.12.19.

    """
    def __init__(self, maxSaccadeDurationMs:float = 80, minSampleConfidence:float = 0.5, classification:int = CLASSIFICATION['TERNARY']):
        self.maxSaccadeDurationMs = maxSaccadeDurationMs
        self.minSampleConfidence = minSampleConfidence
        self.classification = classification


        #TODO maybe change to list
        self.window = deque()
        self.cur  = IBDT_Data(base=GazeDataEntry(ts=0.0, confidence=0.0, x=0.0, y=0.0))
        self.prev = IBDT_Data(base=GazeDataEntry(ts=0.0, confidence=0.0, x=0.0, y=0.0))

        self.firstPoint = False




        self.model = None

        self.fIdx = 0
        self.sIdx = 0
        self.fMean = None
        self.sMean = None







    #DATA calculating methods
    def addPoint(self, entry:object) -> None:
        """Calculates velocity and classifies event type of the given sample, if already trained.

        Not a method for aggregating data samples. Method is for using the classifier.

        :param entry: IBDT_Data to classify event on.
        :return:
        """
        entry.base.classification = MOVEMENT['UNDEF']

        #Low confidence, ignore it
        if entry.base.confidence < self.minSampleConfidence:
            return None



        #Add new point to window and update previous valid point
        self.window.append( entry )
        self.prev = self.cur
        self.cur = self.window[len(self.window)-1]

        #Remove old entries from window
        while True:
            #TODO math.abs() needed??
            if (self.cur.base.ts - self.window[0].base.ts) > (2*self.maxSaccadeDurationMs):
                self.window.popleft()
            else:
                break


        #First point being classified is a special case (since we classify interframe periods)
        if not self.prev:
            self.cur.base.classification = MOVEMENT['UNDEF']
            entry.base.classification = self.cur.base.classification
            return None



        #We have an intersample period, let's classify it
        self.cur.base.v = self.estimateVelocity(self.cur, self.prev)

        #Update the priors
        self.updatePursuitPrior()
        self.cur.fixation.prior = 1 - self.cur.pursuit.prior
        self.cur.saccade.prior = self.cur.fixation.prior


        #Update the likelihoods
        self.updatePursuitLikelihood()
        self.updateFixationAndSaccadeLikelihood()


        #Update the posteriors
        self.cur.pursuit.update()
        self.cur.fixation.update()
        self.cur.saccade.update()



        #Decision
        if self.classification == CLASSIFICATION['TERNARY']:
            self.ternaryClassification()
        elif self.classification == CLASSIFICATION['BINARY']:
            self.binaryClassification()


        entry.classification = self.cur.base.classification




    def train(self, gaze:list) -> None:
        """Perform training on the data specified, split velocity means on 2 clusters and update model hyperparameters.

        :param gaze: list of IBDT_Data to train on.
        :return:
        """
        samples = deque()



        #Find first valid sample
        for index in range(0, len(gaze)):
            previous = gaze[index]
            if (previous != gaze[len(gaze)-1]) and (previous.base.confidence < self.minSampleConfidence):
                previous.base.v = np.nan
                continue
            else:
                break


        #Estimate velocities for remaining training samples
        #TODO refactor to apply() on dataframe
        for index2 in range(index+1, len(gaze)):
            g = gaze[index2]
            #not fully applicable to SMI data
            if g.base.confidence < self.minSampleConfidence:
                g.base.v = np.nan
                continue


            g.base.v = self.estimateVelocity( g, previous )
            if not np.isnan(g.base.v):
                samples.append(g.base.v)

            previous = g




        self.model = cv2.ml.EM_create()
        self.model.setClustersNumber(2)
        self.model.setCovarianceMatrixType(cv2.ml.EM_COV_MAT_GENERIC)
        #TODO + or binary OR??
        self.model.setTermCriteria((cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 15000, 1e-6))
        self.model.trainEM(np.array(samples))



        self.fIdx = 0
        self.sIdx = 1
        means = self.model.getMeans()
        #higher mean velocities are saccades
        if means[0] > means[1]:
            self.fIdx = 1
            self.sIdx = 0

        self.fMean = means[self.fIdx]
        self.sMean = means[self.sIdx]






    def estimateVelocity(self, cur:object, prev:object) -> float:
        """Simple velocity, no smoothing, no angular speed.

        :param cur:
        :param prev:
        :return: velocity from trigonometric distance (incorrect)
        """
        #TODO simple trigonometric distance, must be cosine law for spherical eye model
        dist = cv2.norm( np.array([cur.base.x, cur.base.y]), np.array([prev.base.x, prev.base.y]) )
        dt = cur.base.ts - prev.base.ts
        return dist / dt



    def runJob(self, data:DataFrame,  maxSaccadeDurationMs:float, minSampleConfidence:float, classification:int) -> list:
        """Sets classifier parameters, runs classification and returns list of specified event type.

        :param data: pandas dataframe with 4 columns - time(ms), validity(higher is more valid), x(px or mm), y(px or mm).
        :param maxSaccadeDurationMs: saccades longer than this will not be classified as saccades.
        :param minSampleConfidence: validity lower than this will be considered undefined sample.
        :param classification: int code whether to classify pursuits or fixations and saccades only.
        :return: list of IBDT_Data with events classified.
        """
        self.maxSaccadeDurationMs = maxSaccadeDurationMs
        self.minSampleConfidence = minSampleConfidence
        self.classification = classification


        #----
        ibdtData = []
        for index, row in data.iterrows():
            ibdtData.append(IBDT_Data( base=GazeDataEntry(ts=row[0], confidence=row[1], x=row[2], y=row[3]) ))

        #----
        self.train(ibdtData)
        for pt in ibdtData:
            self.addPoint(pt)
        self.result = ibdtData


        return self.result



    def getResultFiltered(self) -> tuple:
        """Parses result of classification, finds event time borders, calculates durations.

        :return: tuple of 3 dataframes - fixations, saccades, smooth pursuits.
        """
        outAr = []
        for pt in self.result:
            outAr.append([pt.base.ts / 1000, pt.base.classification])
        output = DataFrame(outAr, columns=['Time', 'EventId'])

        #----
        #выделяем границы всех найденных событий
        #TODO можно добавить подсчет статистики - min,max,mean velocity событий
        classDiff = np.hstack((1, np.diff(output['EventId'])))
        nonzero = output[classDiff!=0]
        durations = np.hstack((np.diff(nonzero['Time']), np.nan))
        nonzero.insert(1, 'Duration', durations)

        allEvents = (nonzero.loc[nonzero['EventId'] == MOVEMENT['FIXATION']],
                     nonzero.loc[nonzero['EventId'] == MOVEMENT['SACCADE']],
                     nonzero.loc[nonzero['EventId'] == MOVEMENT['PURSUIT']]
                     )

        return allEvents








    #UPDATE methods
    def updatePursuitPrior(self) -> None:
        """Calculates mean of all ?but last window values.

        :return:
        """
        #TODO refactor whole method to list comprehension
        previousLikelihoods = []
        for index in range(0, len(self.window)-1):
            d = self.window[index]
            previousLikelihoods.append(d.pursuit.likelihood)

        self.cur.pursuit.prior = np.mean(previousLikelihoods)




    def updatePursuitLikelihood(self) -> None:
        """Calculates proportion of all but first velocities which values fall between model hyperparameters.

        :return:
        """
        if len(self.window) < 2:
            return None

        movement = 0.0
        for index in range(1, len(self.window)):
            #if (d-v > 0) #original
            d = self.window[index]
            # adaptive: don't activate with too small or too large movements
            if (d.base.v > self.fMean) and (d.base.v < self.sMean):
                movement = movement+1

        n = len(self.window)-1
        movementRatio = float(movement / n)
        self.cur.pursuit.likelihood = movementRatio





    def updateFixationAndSaccadeLikelihood(self) -> None:
        """Queries the model for predicted likelihoods, writes them to cur sample.

        :return:
        """
        if self.cur.base.v < self.fMean:
            self.cur.fixation.likelihood = 1
            self.cur.saccade.likelihood = 0
            return None

        if self.cur.base.v > self.sMean:
            self.cur.fixation.likelihood = 0
            self.cur.saccade.likelihood = 1
            return None


        sample = np.array(self.cur.base.v)
        try:
            likelihoods = self.model.predict( sample )[1][0]
            self.cur.fixation.likelihood = likelihoods[self.fIdx]
            self.cur.saccade.likelihood = likelihoods[self.sIdx]
        #all zeros in sample
        except cv2.error:
            self.cur.fixation.likelihood = 0.0
            self.cur.saccade.likelihood = 0.0






    #STATUS methods
    def binaryClassification(self) -> None:
        """Simple 2-class likelihood comparison.

        :return:
        """
        if self.cur.fixation.likelihood > self.cur.saccade.likelihood:
            self.cur.classification = MOVEMENT['FIXATION']
        else:
            self.cur.classification = MOVEMENT['SACCADE']




    def ternaryClassification(self) -> None:
        """3-class Bayesian posterior comparison.

        :return:
        """
        #Class that maximizes posterior probability
        maxPosterior = self.cur.fixation.posterior
        self.cur.base.classification = MOVEMENT['FIXATION']


        if self.cur.saccade.posterior > maxPosterior:
            self.cur.base.classification = MOVEMENT['SACCADE']
            maxPosterior = self.cur.saccade.posterior

        if self.cur.pursuit.posterior > maxPosterior:
            self.cur.base.classification = MOVEMENT['PURSUIT']



        #Catch up saccades as saccades
        if self.cur.base.v > self.sMean:
            self.cur.base.classification = MOVEMENT['SACCADE']








#----
class IBDT_Prob():
    """Helper class
    Contains attributes of a data sample.

    """
    def __init__(self, prior:float = 0.0, likelihood:float = 0.0, posterior:float = 0.0):
        self.prior = prior
        self.likelihood = likelihood
        self.posterior = posterior


    def update(self) -> None:
        """Posterior calculation.

        :param self:
        :return:
        """
        self.posterior = self.prior * self.likelihood






class IBDT_Data():
    """Helper class
    Makes a data sample.

    """
    #TODO adapt for direct dataframe input
    def __init__(self, base:GazeDataEntry):
        self.base = base

        self.pursuit = IBDT_Prob()
        self.fixation = IBDT_Prob()
        self.saccade = IBDT_Prob()


