#memory.limit(2047)


#----
#INPUT
#!никакой кириллицы в пути
workPath<-"e://projects//grants//RSCF2018//dataset//zhegallo//data-et//"
participantIds <- c(
   "1_ex-CSB_2015_06_27_1209",
  "01_ex-CSB_2015_07_02_1208",
   "2_ex-CSB_2015_06_27_1237",
  "02_ex-CSB_2015_07_02_1232",
   "3_ex-CSB_2015_06_27_1306",
  "03_ex-CSB_2015_07_02_1258",
   "4_ex-CSB_2015_06_27_1336",
  "5_ex-CSB_2015_06_27_1406",
   "05_ex-CSB_2015_07_02_1323",
  "06_ex-CSB_2015_07_02_1346",
   "7_ex-CSB_2015_06_27_1429",
  "07_ex-CSB_2015_07_02_1415",
   "8_ex-CSB_2015_06_27_1454",
  "08_ex-CSB_2015_07_02_1439",
   "9_ex-CSB_2015_06_27_1522",
  "09_ex-CSB_2015_07_02_1501",
  "10_ex-CSB_2015_06_27_1547",
  "10_ex-CSB_2015_07_02_1521",
  "11_ex-CSB_2015_06_27_1608",
  "11_ex-CSB_2015_07_02_1543",
  "12_ex-CSB_2015_06_27_1631",
  "12_ex-CSB_2015_07_02_1604",
  "13_ex-CSB_2015_06_27_1652",
  "13_ex-CSB_2015_07_02_1627",
  "14_ex-CSB_2015_06_27_1713",
  "14_ex-CSB_2015_07_02_1647",
  "15_ex-CSB_2015_06_27_1734",
  "15_ex-CSB_2015_07_02_1709",
  "16_ex-CSB_2015_06_27_1834",
  "16_ex-CSB_2015_07_02_1733",
  "18_ex-CSB_2015_07_02_1754",
  "19_ex-CSB_2015_07_02_1829",
  "20_ex-CSB_2015_07_02_1849",
  "21_ex-CSB_2015_07_02_1914",
  "22_ex-CSB_2015_07_02_1935"
)
samplesFiles <- paste(workPath, paste0(participantIds," Samples.txt"), sep="/")
rdataFiles <- gsub(".txt", ".RData", samplesFiles)




#----
#metadata
screenWidthPx  <- 1280
screenHeightPx <- 1024
screenWidthMm  <- 376
screenHeightMm <- 301
headDistanceMm <- 635
frameRate      <- 120

screenWidthDeg  <- atan(screenWidthMm/2/headDistanceMm) *180/pi*2
screenHeightDeg <- atan(screenHeightMm/2/headDistanceMm)*180/pi*2
screenHResMm    <- screenWidthMm/screenWidthPx
screenVResMm    <- screenHeightMm/screenHeightPx





#----
fixDotPattern <- "Fix"
stimPattern   <- ".avi"

#data reader function
require(data.table)
require(signal)
require(geosphere)
require(SphericalCubature)
readSamples <- function() {
  samplesHeader <- readLines(samplesFile,50)
  samplesFileSkip<-grep("\\d+\\t[SMP|MSG]",samplesHeader)[1]-2
  samplesColclasses<-strsplit(samplesHeader[samplesFileSkip+1],"\t")[[1]]
  samplesColclasses<-gsub("Trial|.*Raw.*|.* CR.*|.*Dia.*|Timing|.*Valid.*|.*Plane|Pupil Confidence|.*EPOS.*|.*GVEC.*|Aux.*", "NULL",samplesColclasses)
  samplesColclasses<-gsub("Time|.*POR.*", "numeric",samplesColclasses)
  samplesColclasses<-gsub("Latency|Trigger", "integer",samplesColclasses)
  samplesColclasses<-gsub("Type|Frame", "character",samplesColclasses)
  samplesColclasses[4]<-"character"
  zeroTime<<-as.numeric(strsplit(samplesHeader[samplesFileSkip+2],"\t")[[1]][1])
  #
  print("Reading samples...")
  samplesData <- read.delim(samplesFile,skip=samplesFileSkip,row.names=NULL, colClasses=samplesColclasses)
  samplesData <- data.table(samplesData)
  setnames(samplesData,gsub("\\.","",colnames(samplesData)))
  setkey(samplesData,"Type")
  samples<<-samplesData[J("SMP")]
  samples[,Type:=NULL]
  samples[,2:=as.numeric(samples[,2,with=FALSE][[1]])]
  samples[,Time:=(Time-zeroTime)/10^6]
  #
  messages<<-samplesData[J("MSG")]
  messages[,Type:=NULL]
  messages[,3:ncol(messages) := NULL]
  setnames(messages,c("Time","Text"))
  messages[,Text:=gsub("# Message: ","",Text)]
  messages[,Time:=(Time-zeroTime)/10^6]
  messages<<-as.data.frame(messages)
  #----
  #
  trialMessages<-messages[grep(fixDotPattern,messages[,"Text"]),]
  smpIndices<<-numeric()
  print("Indexing trials...")
  for (msgInt in seq_along(trialMessages[,"Time"])){
    time<-trialMessages[msgInt,"Time"]
    ind<-last(samples[Time %between% c(0,time),which=TRUE])
    smpIndices[msgInt]<<-ind
  }
  smpIndices<<-c(smpIndices,nrow(samples))
  #----
  #читаем только 1 канал, если они одинаковые (RED-m-HP)
  for (chLetter in c("L","R")) {
    if (length(grep(paste0(chLetter,"PORXpx"),colnames(samples)))) {
      channel<<-chLetter
      samples[,paste0(channel,"PORXMm"):=  (samples[,paste0(channel,"PORXpx"),with=FALSE]-screenWidthPx/2)*screenHResMm]
      samples[,paste0(channel,"PORYMm"):= -(samples[,paste0(channel,"PORYpx"),with=FALSE]-screenHeightPx/2)*screenVResMm]
      samples[,paste0(channel,"PORXDeg"):=atan(samples[,paste0(channel,"PORXMm"),with=FALSE]/headDistanceMm)/pi*180]
      samples[,paste0(channel,"PORYDeg"):=atan(samples[,paste0(channel,"PORYMm"),with=FALSE]/headDistanceMm)/pi*180]
      #
      lastIndex<-1
      print("Smoothing...")
      #using SPLINE, SGOLAY
      for (smpInt in seq_along(smpIndices)){
        index<-smpIndices[smpInt]
        samples[lastIndex:index, paste0(channel,"SplinePORXpx") := smooth.spline(samples[lastIndex:index, paste0(channel,"PORXpx"),with=FALSE], spar=.8,all.knots=TRUE,keep.data=FALSE)$y]
        samples[lastIndex:index, paste0(channel,"SplinePORYpx") := smooth.spline(samples[lastIndex:index, paste0(channel,"PORYpx"),with=FALSE], spar=.8,all.knots=TRUE,keep.data=FALSE)$y]
        #samples[lastIndex:index, paste0(channel,"SgolayPORXpx") := sgolayfilt(samples[lastIndex:index, paste0(channel,"PORXpx"),with=FALSE][[1]],2,15)]
        #samples[lastIndex:index, paste0(channel,"SgolayPORYpx") := sgolayfilt(samples[lastIndex:index, paste0(channel,"PORYpx"),with=FALSE][[1]],2,15)]
        lastIndex <- index+1
      }
      samples[,paste0(channel,"SplinePORXMm"):=  (samples[,paste0(channel,"SplinePORXpx"),with=FALSE]-screenWidthPx/2)*screenHResMm]
      samples[,paste0(channel,"SplinePORYMm"):= -(samples[,paste0(channel,"SplinePORYpx"),with=FALSE]-screenHeightPx/2)*screenVResMm]
      samples[,paste0(channel,"SplinePORXDeg"):=atan(samples[,paste0(channel,"SplinePORXMm"),with=FALSE]/headDistanceMm)/pi*180]
      samples[,paste0(channel,"SplinePORYDeg"):=atan(samples[,paste0(channel,"SplinePORYMm"),with=FALSE]/headDistanceMm)/pi*180]
      #samples[,paste0(channel,"SgolayPORXMm"):=  (samples[,paste0(channel,"SgolayPORXpx"),with=FALSE]-screenWidthPx/2)*screenHResMm]
      #samples[,paste0(channel,"SgolayPORYMm"):= -(samples[,paste0(channel,"SgolayPORYpx"),with=FALSE]-screenHeightPx/2)*screenVResMm]
      #samples[,paste0(channel,"SgolayPORXDeg"):=atan(samples[,paste0(channel,"SgolayPORXMm"),with=FALSE]/headDistanceMm)/pi*180]
      #samples[,paste0(channel,"SgolayPORYDeg"):=atan(samples[,paste0(channel,"SgolayPORYMm"),with=FALSE]/headDistanceMm)/pi*180]
      #VELOCITY
      #2018.12.05 посчитаем скорость от несглаженного сигнала
      veloTmp <- data.table(tmp=rep(0,nrow(samples)))
      veloTmp[,screenDistMm     := sqrt( samples[,paste0(channel,"PORXMm"),with=FALSE]^2 + samples[,paste0(channel,"PORYMm"),with=FALSE]^2 )]
      veloTmp[,screenDistMmPrev := c(0,screenDistMm[-length(screenDistMm)])]
      veloTmp[,screenAngleRad   := c( 0,diff( atan2(samples[,paste0(channel,"PORYMm"),with=FALSE][[1]], samples[,paste0(channel,"PORXMm"),with=FALSE][[1]]) ) )]
      veloTmp[,eyeDistMm        := sqrt( screenDistMm^2 + headDistanceMm^2)]
      veloTmp[,eyeDistMmPrev    := c(0,eyeDistMm[-length(eyeDistMm)])]
      veloTmp[,screenScanpathMm := screenDistMm^2 + screenDistMmPrev^2 - 2*screenDistMm*screenDistMmPrev * cos(screenAngleRad)]
      veloTmp[,eyeAngleRad      := acos(pmax(pmin( (eyeDistMm^2 + eyeDistMmPrev^2 - screenScanpathMm^2) / (2*eyeDistMm*eyeDistMmPrev), 1.0),-1.0) )]
      veloTmp[,timelag          := c(1,diff(samples[,Time]))]
      samples[,paste0(channel,"Velocity") := veloTmp[,eyeAngleRad]/pi*180/veloTmp[,timelag]]
      #от сглаженного
      veloTmp<-data.table(tmp=rep(0,nrow(samples)))
      veloTmp[,screenDistMm:=sqrt( samples[,paste0(channel,"SplinePORXMm"),with=FALSE]^2 + samples[,paste0(channel,"SplinePORYMm"),with=FALSE]^2 )]
      veloTmp[,screenDistMmPrev:=c(0,screenDistMm[-length(screenDistMm)])]
      veloTmp[,screenAngleRad:=c( 0,diff( atan2(samples[,paste0(channel,"SplinePORYMm"),with=FALSE][[1]], samples[,paste0(channel,"SplinePORXMm"),with=FALSE][[1]]) ) )]
      veloTmp[,eyeDistMm:=sqrt( screenDistMm^2 + headDistanceMm^2)]
      veloTmp[,eyeDistMmPrev:=c(0,eyeDistMm[-length(eyeDistMm)])]
      veloTmp[,screenScanpathMm:=screenDistMm^2 + screenDistMmPrev^2 - 2*screenDistMm*screenDistMmPrev * cos(screenAngleRad)]
      veloTmp[,eyeAngleRad:=acos(pmax(pmin( (eyeDistMm^2 + eyeDistMmPrev^2 - screenScanpathMm^2) / (2*eyeDistMm*eyeDistMmPrev), 1.0),-1.0) )]
      veloTmp[,timelag:=c(1,diff(samples[,Time]))]
      samples[,paste0(channel,"SplineVelocity"):=veloTmp[,eyeAngleRad]/pi*180/veloTmp[,timelag]]
      #
      #veloTmp<-data.table(tmp=rep(0,nrow(samples)))
      #veloTmp[,screenDistMm:=sqrt( samples[,paste0(channel,"SgolayPORXMm"),with=FALSE]^2 + samples[,paste0(channel,"SgolayPORYMm"),with=FALSE]^2 )]
      #veloTmp[,screenDistMmPrev:=c(0,screenDistMm[-length(screenDistMm)])]
      #veloTmp[,screenAngleRad:=c( 0,diff( atan2(samples[,paste0(channel,"SgolayPORYMm"),with=FALSE][[1]], samples[,paste0(channel,"SgolayPORXMm"),with=FALSE][[1]]) ) )]
      #veloTmp[,eyeDistMm:=sqrt( screenDistMm^2 + headDistanceMm^2)]
      #veloTmp[,eyeDistMmPrev:=c(0,eyeDistMm[-length(eyeDistMm)])]
      #veloTmp[,screenScanpathMm:=screenDistMm^2 + screenDistMmPrev^2 - 2*screenDistMm*screenDistMmPrev * cos(screenAngleRad)]
      #veloTmp[,eyeAngleRad:=acos(pmax(pmin( (eyeDistMm^2 + eyeDistMmPrev^2 - screenScanpathMm^2) / (2*eyeDistMm*eyeDistMmPrev), 1.0),-1.0) )]
      #veloTmp[,timelag:=c(1,diff(samples[,Time]))]
      #samples[,paste0(channel,"SgolayVelocity"):=veloTmp[,eyeAngleRad]/pi*180/veloTmp[,timelag]]
    }
  }
  samples[,c("LRawXpx","Latency","Frame"):=NULL]
}





#----
#PLOTTING functions
spatialPlot <- function() {
  plotSamplesSet <<- samples[Time %between% c(plotStartTime, plotStartTime+plotWidthS)]
  plotSamplesSet <<- as.data.frame(plotSamplesSet)
  #
  plot(0, type="n",
       main=plotStartTime+plotWidthS, xlab="Gaze X (°)",ylab="Gaze Y (°)",
       xlim=c(-screenWidthDeg/2,screenWidthDeg/2), ylim=c(-screenHeightDeg/2,screenHeightDeg/2))
  
  grid()
  abline(h=0, v=0, lty='dashed', col='lightgrey')
  #lines(plotSamplesSet[,paste0(channel,"SmoothPORXDeg")],plotSamplesSet[,paste0(channel,"SmoothPORYDeg")],lwd=lineWidth*2,col=plotCol)
  #
  #уходы в угол экрана прорисовываются штрихом
  xNans <<- plotSamplesSet[,paste0(channel,"PORXDeg")] == -screenWidthDeg/2
  xNansNum <<- unique(c(which(xNans)-1, which(xNans)+1))
  yNans <<- plotSamplesSet[,paste0(channel,"PORYDeg")] == screenHeightDeg/2
  yNansNum <<- unique(c(which(yNans)-1, which(yNans)+1))
  allNansNum <<- unique(c(xNansNum, yNansNum))
  lines(plotSamplesSet[allNansNum,paste0(channel,"PORXDeg")], plotSamplesSet[allNansNum,paste0(channel,"PORYDeg")], lwd=lineWidth,lty='dotted',col='chocolate')
  #
  #plotSamplesSetNanned <<- plotSamplesSet
  if (length(xNans)) {
    plotSamplesSet[xNans, c(paste0(channel,"PORXDeg"), paste0(channel,"Velocity"), paste0(channel,"SplineVelocity"), paste0(channel,"SgolayVelocity"))] <<- NaN
  }
  if (length(yNans)) {
    plotSamplesSet[yNans, c(paste0(channel,"PORYDeg"), paste0(channel,"Velocity"), paste0(channel,"SplineVelocity"), paste0(channel,"SgolayVelocity"))] <<- NaN
  }
  #validSmpL <<- plotSamplesSet[,paste0(channel,"PORXDeg")]!=-screenWidthDeg/2 & plotSamplesSet[,paste0(channel,"PORYDeg")]!=screenHeightDeg/2
  #plotSamplesSet <<- plotSamplesSet[validSmpL,]
  lines(plotSamplesSet[,paste0(channel,"SplinePORXDeg")], plotSamplesSet[,paste0(channel,"SplinePORYDeg")], lwd=lineWidth,col='yellow')
  lines(plotSamplesSet[,paste0(channel,"PORXDeg")], plotSamplesSet[,paste0(channel,"PORYDeg")], lwd=lineWidth*2,col='chocolate')
  points(tail(plotSamplesSet[,paste0(channel,"PORXDeg")],1), tail(plotSamplesSet[,paste0(channel,"PORYDeg")],1), pch=3)
  #points(tail(plotSamplesSet[,paste0(channel,"SmoothPORXDeg")],1),tail(plotSamplesSet[,paste0(channel,"SmoothPORYDeg")],1),pch=3)
  plotEvents("messages", "spatial")
}


plotSamples <- function() {
  plot(0,type="n",
       xlab="Time (s)",ylab="Gaze (°)",
       xlim=c(plotStartTime,plotStartTime+plotWidthS), ylim=c(-screenWidthDeg/2,screenWidthDeg/2))
  grid()
  abline(h=0, lty='dashed', col='lightgrey')
  abline(h=c(-screenWidthDeg/2,screenWidthDeg/2), lty='dashed', col='pink',lwd=lineWidth/2)
  abline(h=c(-screenHeightDeg/2,screenHeightDeg/2), lty='dashed', col='skyblue',lwd=lineWidth/2)
  plotEvents("messages", "full")
  lines(plotSamplesSet[,"Time"],plotSamplesSet[,paste0(channel,"SplinePORYDeg")],lwd=lineWidth,col="blue")
  lines(plotSamplesSet[,"Time"],plotSamplesSet[,paste0(channel,"SplinePORXDeg")],lwd=lineWidth,col="red")
  #
  #lines(plotSamplesSet[yNansNum,"Time"], plotSamplesSet[yNansNum,paste0(channel,"PORYDeg")], lwd=lineWidth,lty='dotted',col='skyblue')
  #lines(plotSamplesSet[xNansNum,"Time"], plotSamplesSet[xNansNum,paste0(channel,"PORXDeg")], lwd=lineWidth,lty='dotted',col='pink')
  points(plotSamplesSet[,"Time"], plotSamplesSet[,paste0(channel,"PORYDeg")],lwd=lineWidth*2,col="skyblue")
  points(plotSamplesSet[,"Time"], plotSamplesSet[,paste0(channel,"PORXDeg")],lwd=lineWidth*2,col="pink")
}


plotVelocity <- function() {
  plot(0,type="n",
       xlab="Time (s)",ylab="Velocity (°/s)",
       xlim=c(plotStartTime,plotStartTime+plotWidthS),ylim=c(-50,1000))
  grid()
  #empirical saccade median and maximum limits
  abline(h=400, lty='dashed', col='lightgrey')
  abline(h=750, lty='dashed', col='grey')
  plotEvents("messages","full")
  #lines(plotSamplesSet[allNansNum,"Time"], plotSamplesSet[allNansNum,paste0(channel,"Velocity")], lwd=lineWidth,lty='dotted',col='grey')
  #lines(plotSamplesSet[allNansNum,"Time"], plotSamplesSet[allNansNum,paste0(channel,"SplineVelocity")], lwd=lineWidth,lty='dotted',col='peachpuff2')
  #lines(plotSamplesSet[allNansNum,"Time"], plotSamplesSet[allNansNum,paste0(channel,"SgolayVelocity")], lwd=lineWidth,lty='dotted',col='yellowgreen')
  #
  lines(plotSamplesSet[,"Time"], plotSamplesSet[,paste0(channel,"Velocity")],col='grey',lwd=lineWidth*4)
  lines(plotSamplesSet[,"Time"], plotSamplesSet[,paste0(channel,"SplineVelocity")],col='peachpuff2',lwd=lineWidth*2)
  #lines(plotSamplesSet[,"Time"], plotSamplesSet[,paste0(channel,"SgolayVelocity")],col='yellowgreen',lwd=lineWidth*2)
}


plotEvents <- function(type,mode) {
  channelEvents<-get(type)
  plotEvents<-channelEvents[channelEvents$Time>=plotStartTime & channelEvents$Time<plotStartTime+plotWidthS,]
  #
  plotEventsLength<-length(plotEvents[,1])
  if (plotEventsLength!=0) {
    if (type=="messages") {
      if (mode=="full") {
        abline(v=plotEvents$Time,col="skyblue",lty="dashed",lwd=lineWidth*2)
        points(plotEvents$Time,rep(-20,plotEventsLength),col="skyblue",bg="skyblue",pch=2)
      } else if (mode=="spatial") {
        for (messageInt in 1:plotEventsLength) {
          plotMessage<-plotEvents[messageInt,]
          messageSample<-plotSamplesSet[tail(which(plotSamplesSet[,"Time"]<=plotMessage[,"Time"]),1),]
          points(messageSample[,paste0(channel,"PORXDeg")],messageSample[,paste0(channel,"PORYDeg")],col="skyblue",bg="skyblue",pch=2)
        }
      }
    }
  }
}


tempoPlot <- function() {
  windows(width=200,height=3, rescale="fixed")
  opar<<-par(pty="m",mai=c(.5,.6,.2,.2))
  plotSamples()
  par(opar)
  #dev.copy2pdf(file=paste0(workPath[dirInt],"img/tempo_",plotStartTime,".pdf"),out.type="cairo")
}


imgNum <<- 0
combiPlot <- function(mode='cascade') {
  widthPlotted <<- 0
  if (mode=='cascade') {
    segments <- 5
  } else if (mode=='animation') {
    segments <- 1
  }
  
  while (widthPlotted < cascadeWidthS) {
    if (mode=='cascade') {
      windows(width=5*segments,height=13,rescale="fixed")
    } else if (mode=='animation') {
      imgNum <<- imgNum + 1
      png(file=paste0(workPath,"img/byFrame_",  sprintf('%06d', imgNum),".png"),
          width=5*segments,height=13,units='in',res=150,bg="white")
    }
    opar<<-par(pty="m",mai=c(.5,.6,.2,.2),mfrow=c(3,segments),pin=c(4,3))
    for (i in 1:segments) {
      opar <<- par(mfg=c(1,i))
      spatialPlot()
      opar <<- par(mfg=c(2,i))
      plotSamples()
      opar <<- par(mfg=c(3,i))
      plotVelocity()
      if (mode=='cascade') {
        plotStartTime <<- plotStartTime+plotWidthS
        widthPlotted  <<- widthPlotted+plotWidthS
      } else if (mode=='animation') {
        #здесь задается временной шаг каждого кадра анимации
        plotStartTime <<- plotStartTime+1/frameRate
        widthPlotted  <<- widthPlotted+1/frameRate
      }
    }
    par(opar)
    #выбор пути для файла
    if (mode=='cascade') {
      dev.copy2pdf(file=paste0(workPath,"img/combi_",participantIds[dirInt],"_",plotStartTime,".pdf"),out.type="cairo")
    }
    dev.off()
  }
}






#----
#READING data
dirInt <- 31
print(paste0("Record ",dirInt,"/",length(participantIds)))
samplesFile<-samplesFiles[dirInt]
readSamples()


#helper lists
diff(messages[,'Time'])
fixDotMessageInts <- grep(tolower(fixDotPattern),tolower(messages[,"Text"]))
fixDotMessages    <- messages[fixDotMessageInts,]
stimMessageInts   <- grep(fixDotPattern,messages[,"Text"])+1
stimMessages      <- messages[stimMessageInts,]
endMessagesInts   <- grep(fixDotPattern,messages[,"Text"])+2
#assuming the experiment was run on a 144 Hz display
fixDurS           <- ceiling((stimMessages[,"Time"]-messages[fixDotMessageInts,"Time"]) / (1/144)) * 1/144
stimuliDurS       <- ceiling((messages[endMessagesInts,"Time"]-stimMessages[,"Time"]) / (1/144)) * 1/144



#SANITY CHECK routines (optional)
if (all(samples[,"LPORXpx"]==samples[,"RPORXpx"])) {
  print("L and R channels EQUIVALENT.")
}
all(stimMessages[,"Time"]>fixDotMessages[,"Time"],na.rm=TRUE)
nrow(fixDotMessages)==length(endMessagesInts)
length(endMessagesInts)==nrow(stimMessages)






#----
#now PLOTTING
require('Cairo')
imgPath<-"e://projects//grants//RSCF2018//dataset//zhegallo//"
dir.create(paste0(workPath,"/img/"))
imgW      <- 3.7
imgH      <- 6
lineWidth <- 1.0
plotCol   <- "black"
plotWidthS<- 50/frameRate
#сколько всего прорисовывать блоков для combiPlot
cascadeWidthS <- 65.0


#----
#channel <- "R"
recordData<-data.frame(fixDotInt=1:nrow(fixDotMessages))
recordData[,"participantId"]<-rep(participantIds[dirInt],nrow(fixDotMessages))
plotData  <- recordData


for (plotMessageInt in 1:nrow(plotData)) {
  #смотрим участки сразу после появления стимула
  plotStartTime <- as.numeric(fixDotMessages[plotMessageInt,"Time"][1])
  
  combiPlot(mode='cascade') #cascade, animation
  #dev.off()
}
