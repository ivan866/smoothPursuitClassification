import math, cmath
from datetime import datetime, date, timedelta

import angles

import pandas
from pandas import Series




#TIME formatting methods
def guessTimeFormat(val:object) -> str:
    """Helper method to determine the time strf string.
    
    :param val: Time string to try to parse.
    :return: Format string.
    """
    if type(val) is not str:
        val=str(val)

    formats = ['%H:%M:%S.%f', '%M:%S.%f', '%M:%S', '%S.%f', '%S']
    for fmt in formats:
        try:
            datetime.strptime(val, fmt)
        except ValueError:
            try:
                pandas.to_datetime(val, unit='s')
            except ValueError:
                continue
            break
        break
    #print('Time format of ' + val + ' string is guessed as ' + fmt + '.')
    return fmt


#FIXME valueerror if format =s.f and s>61
def parseTime(val:object = 0) -> timedelta:
    """Helper method to convert time strings to datetime objects.

    Agnostic of time string format.

    :param val: Time string or float.
    :return: timedelta object.
    """
    val=str(val)
    fmt=guessTimeFormat(val)
    try:
        parsed=datetime.strptime(val, fmt)
    except ValueError:
        parsed=pandas.to_datetime(val, unit='s')
    return datetime.combine(date.min,parsed.time())-datetime.min


def parseTimeV(data:Series) -> Series:
    """Vectorized version of parseTime method.

    :param data: pandas Series object.
    :return: Same object with values converted to timedelta.
    """
    if data.name=='Time' or data.name=='Recording timestamp':
        return pandas.to_timedelta(data.astype(float), unit='s')
    else:
        return pandas.to_datetime(data.astype(str), infer_datetime_format=True) - date.today()




#CONVERSION methods
def getSeparation(x1:float,y1:float, x2:float,y2:float,  z:float,  mode:str) -> float:
    """Returns angular separation between two angles on a unit sphere.

    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :param z: depth, in mm
    :param mode: whether coordinates are passed in mm or degrees
    :return: angle in degrees
    """
    if mode=='fromCartesian':
        lon1 = cmath.polar(complex(x1, z))[1]-math.pi/2
        lat1 = cmath.polar(complex(y1, z))[1]-math.pi/2
        lon2 = cmath.polar(complex(x2, z))[1]-math.pi/2
        lat2 = cmath.polar(complex(y2, z))[1]-math.pi/2

        sep = angles.sep(lon1,lat1, lon2,lat2)
    elif mode=='fromPolar':
        sep = angles.sep(math.radians(x1),math.radians(y1), math.radians(x2),math.radians(y2))


    return math.degrees(sep)
