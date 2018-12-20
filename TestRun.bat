REM python -m unittest discover -s tests
python SmoothPursuitClassification.py -s=./TestSettings.xml --algo=ibdt
python SmoothPursuitClassification.py -s=./TestSettings.xml --smooth=spline --algo=ibdt

python SmoothPursuitClassification.py -s=./TestSettings.xml --smooth=savgol --algo=ivt
python SmoothPursuitClassification.py -s=./TestSettings.xml --smooth=spline --algo=ivt
python SmoothPursuitClassification.py -s=./TestSettings.xml --smooth=conv --algo=ivt