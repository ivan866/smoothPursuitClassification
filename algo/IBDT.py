from collections import deque
import numpy as np
#TODO probably cv2.Algorithm
import algorithm



#core
import cv2
from cv2 import ml



from algo.IBDT import IBDT_Prob
from algo.IBDT import IBDT_Data
from algo.IBDT import CLASSIFICATION
from algo import GazeData
from algo.GazeData import GazeDataEntry
from algo.GazeData import MOVEMENT








CLASSIFICATION = {'TERNARY':0,
                  'BINARY':1
                  }



class IBDT():
    """Main class of the algorithm
    Contains methods for training and data manipulation.

    Confidence column is not meaningful for SMI eyetrackers. Replaced by 1-validity.

    Ported by ivan866 on 2018.12.08.

    """
    def __init__(self, maxSaccadeDurationMs:float = 80, minSampleConfidence:float = 0.5, classification:int = CLASSIFICATION['TERNARY']):
        self.maxSaccadeDurationMs = maxSaccadeDurationMs
        self.minSampleConfidence = minSampleConfidence
        self.classification = classification


        # IBDT_Data
        #TODO maybe change to list
        self.window = deque()
        self.cur  = IBDT_Data(base=GazeDataEntry(ts=0.0, confidence=0.0, x=0.0, y=0.0))
        self.prev = IBDT_Data(base=GazeDataEntry(ts=0.0, confidence=0.0, x=0.0, y=0.0))

        # True
        self.firstPoint = False




        # TODO Ptr<>
        self.model = cv2.ml.EM()

        # TODO ?
        self.fIdx = 0
        self.sIdx = 0
        self.fMean = None
        self.sMean = None







    #DATA calculating methods
    def addPoint(self, entry:GazeDataEntry) -> None:
        """Adds a point to the data np.array, calculates velocity and classifies event type of the given sample, if already trained.

        :return:
        """
        entry.classification = MOVEMENT['UNDEF']

        #Low confidence, ignore it
        if entry.confidence < self.minSampleConfidence:
            return None



        #Add new point to window and update previous valid point
        self.window.append( entry )
        self.prev = self.cur
        self.cur = self.window[len(self.window)]

        #Remove old entries from window
        while True:
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


        #TODO ??must be a returned value instead of original pointer
        entry.classification = self.cur.base.classification




    def train(self, gaze:list) -> None:
        """Perform training on the data specified, split velocity means on 2 clusters and update model hyperparameters.

        :return:
        """
        samples = cv2.Mat_()



        #Find first valid sample
        for index in range(0, len(gaze)):
            previous = gaze[index]
            if (previous != gaze[len(gaze)]) and (previous.base.confidence < self.minSampleConfidence):
                #TODO byref or byval assignment?
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
                samples.push_back(g.base.v)

            previous = g




        self.model = cv2.ml.EM.create()
        self.model.setClustersNumber(2)
        # default is 2
        self.model.setCovarianceMatrixType(cv2.ml.EM.COV_MAT_GENERIC)
        self.model.setTermCriteria( cv2.TermCriteria(cv2.TermCriteria_COUNT + cv2.TermCriteria_EPS, 15000, 1e-6) )
        self.model.trainEM(samples)



        self.fIdx = 0
        self.sIdx = 1
        means = self.model.getMeans()
        #higher mean velocities are saccades
        if means.at(0) > means.at(1):
            self.fIdx = 1
            self.sIdx = 0

        self.fMean = means.at(self.fIdx)
        self.sMean = means.at(self.sIdx)






    def estimateVelocity(self, cur:GazeDataEntry, prev:GazeDataEntry) -> float:
        """Simple velocity, no smoothing, no angular speed.

        :param cur:
        :param prev:
        :return: velocity from trigonometric distance (incorrect)
        """
        #TODO simple trigonometric distance, must be cosine law for spherical eye model
        dist = cv2.norm( cv2.Point2f(cur.base.x, cur.base.y) - cv2.Point2f(prev.base.x, prev.base.y) )
        dt = cur.base.ts - prev.base.ts
        return dist / dt







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


        sample = cv2.Mat_(1,1, self.cur.base.v)
        likelihoods = cv.Mat_()
        self.model.predict( sample, likelihoods )
        self.cur.fixation.likelihood = likelihoods.at(self.fIdx)
        self.cur.saccade.likelihood = likelihoods.at(self.sIdx)






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
    def __init__(self, base:GazeDataEntry):
        self.base = base

        self.pursuit = IBDT_Prob()
        self.fixation = IBDT_Prob()
        self.saccade = IBDT_Prob()


