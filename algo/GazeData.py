from numpy import array


import cv2



from algo.GazeData import MOVEMENT









#TODO keep here or move to class init
MOVEMENT = {'FIXATION':0,
            'SACCADE':1,
            'PURSUIT':2,
            'NOISE':3,
            'UNDEF':4
            }




class GazeDataEntry():
    """Helper class
    IS a data sample with only 4 values: timestamp, eyetracking quality confidence, X and Y coordinates.

    """
    def __init__(self, ts:float, confidence:float, x:float, y:float):
        self.ts = ts

        self.confidence = confidence

        self.x = x
        self.y = y

        self.v = 0.0

        self.classification = MOVEMENT['UNDEF']





    def isFixation(self) -> bool:
        """

        :return:
        """
        return self.classification == MOVEMENT['FIXATION']


    def isSaccade(self) -> bool:
        """

        :return:
        """
        return self.classification == MOVEMENT['SACCADE']


    def isPursuit(self) -> bool:
        """

        :return:
        """
        return self.classification == MOVEMENT['PURSUIT']




    def isNoise(self) -> bool:
        """

        :return:
        """
        return self.classification == MOVEMENT['NOISE']




    def isUndef(self) -> bool:
        """

        :return:
        """
        return self.classification == MOVEMENT['UNDEF']



    def pause(self) -> None:
        """

        :return:
        """
        #return int(0)
        pass	#?


