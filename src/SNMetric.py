import numpy

from lsst.sims.maf.metrics.baseMetric import BaseMetric

class SNMetric(BaseMetric):
    """Measure how many time serries meet a given time and filter distribution requirement """
    def __init__(self, metricName='SNMetric', nightcol='night', filtercol='filter',
                 m5col='fivesigma_modified', units='', redshift=0.,
                 Tmin = -20., Tmax = 60., Nbetween=7, Nfilt=2, Tless = -5., Nless=1,
                 Tmore = 30., Nmore=1, peakGap=15., snrCut=10., singleDepthLimit=23., resolution=5., badval=666,
                 T0=30.,
                 uniqueBlocks=False, **kwargs):
        """
        redshift = redshift of the SN.  Used to scale observing dates to SN restframe.
        Tmin = the minimum day to consider the SN.  
        Tmax = the maximum to consider.
        Nbetween = the number of observations to demand between Tmin and Tmax
        Nfilt = number of unique filters that must observe the SN above the snrCut
        Tless = minimum time to consider 'near peak'
        Tmore = max time to consider 'near peak'
        Nless = number of observations to demand before Tless
        Nmore = number of observations to demand after Tmore
        peakGap = maximum gap alowed between observations in the 'near peak' time
        snrCut = require snr above this limit when counting Nfilt XXX-not yet implemented
        singleDepthLimit = require observations in Nfilt different filters to be this
        deep near the peak.  This is a rough approximation for the Science Book
        requirements for a SNR cut.  Ideally, one would import a time-variable SN SED,
        redshift it, and make filter-keyed dictionary of interpolation objects so the
        magnitude of the SN could be calculated at each observation and then use the m5col
        to compute a SNR.
        resolution = time step (days) to consider when calculating observing windows
        uniqueBlocks = should the code count the number of unique sequences that meet
        the requirements (True), or should all sequences that meet the conditions
        be counted (False).

        The filter centers are shifted to the SN restframe and only observations
        with filters between 300 < lam_rest < 900 nm are included

        In the science book, the metric demands Nfilt observations above a SNR cut.
        Here, we demand Nfilt observations near the peak with a given singleDepthLimt."""
        
        cols=[nightcol,m5col,filtercol]
        self.nightcol = nightcol
        self.m5col = m5col
        self.filtercol = filtercol
        super(SNMetric, self).__init__(cols, metricName, units=units, **kwargs)
        self.metricDtype = 'object'
        self.units = units
        self.redshift = redshift
        self.Tmin = Tmin
        self.Tmax = Tmax
        self.Nbetween = Nbetween
        self.Nfilt = Nfilt
        self.Tless = Tless
        self.Nless = Nless
        self.Tmore = Tmore
        self.Nmore = Nmore
        self.peakGap = peakGap
        self.snrCut = snrCut
        self.resolution = resolution
        self.uniqueBlocks = uniqueBlocks
        self.filterNames = numpy.array(['u','g','r','i','z','y'])
        self.filterWave = numpy.array([375.,476.,621.,754.,870.,980.])/(1.+self.redshift) # XXX - rough values
        self.filterNames = self.filterNames[numpy.where( (self.filterWave > 300.) & (self.filterWave < 900.))[0]] #XXX make wave limits kwargs?
        self.singleDepthLimit = singleDepthLimit
        self.badval = badval
        self.T0=T0

        # It would make sense to put a dict of interpolation functions here keyed on filter that take time and returns the magnitude of a SN.  So, take a SN SED, redshift it, calc it's mag in each filter.  repeat for multiple time steps.  
        
    def run(self, dataSlice):
        metric=0
        #Figure out the seasons for the pixel
        seasons= SNMetric.splitBySeason(dataSlice,self.T0)
        for s in seasons:
            for filter in self.filterNames:
                for night in s:
                    m5col_ = dataSlice['fivesigma_modified'][numpy.logical_and(dataSlice['night']==night,dataSlice['filter'] == filter)]
                    print filter, night, m5col_
        print shit
                               
        """ """
        # Cut down to only include filters in correct wave range.
        goodFilters = np.in1d(dataSlice['filter'],self.filterNames)
        dataSlice = dataSlice[goodFilters]
        if dataSlice.size == 0:
            return (self.badval, self.badval,self.badval)
        dataSlice.sort(order=self.nightcol)
        time = dataSlice[self.nightcol]-dataSlice[self.nightcol].min()
        time = time/(1.+ self.redshift) # Now days in SN rest frame
        finetime = np.arange(0.,np.ceil(np.max(time)),self.resolution) # Creat time steps to evaluate at
        ind = np.arange(finetime.size) #index for each time point
        right = np.searchsorted( time, finetime+self.Tmax-self.Tmin, side='right') #index for each time point + Tmax - Tmin
        left = np.searchsorted(time, finetime, side='left')
        good = np.where( (right - left) > self.Nbetween)[0] # Demand enough visits in window
        ind = ind[good]
        right = right[good]
        left = left[good]
        result = 0
        maxGap = [] # Record the maximum gap near the peak (in rest-frame days)
        Nobs = [] # Record the total number of observations in a sequence.
        right_side = -1
        for i,index in enumerate(ind):
            if i <= right_side:
                pass
            else:
                visits = dataSlice[left[i]:right[i]]
                t = time[left[i]:right[i]]
                t = t-finetime[index]+self.Tmin
                
                if np.size(np.where(t < self.Tless)[0]) > self.Nless:
                    if np.size(np.where(t > self.Tmore)[0]) > self.Nmore:
                        if np.size(t) > self.Nbetween:
                            ufilters = np.unique(visits[self.filtercol])
                            if np.size(ufilters) >= self.Nfilt: #XXX need to add snr cut here
                                filtersBrightEnough = 0
                                nearPeak = np.where((t > self.Tless) & (t < self.Tmore))
                                ufilters = np.unique(visits[self.filtercol][nearPeak])
                                for f in ufilters:
                                    if np.max(visits[self.m5col][nearPeak][np.where(visits[self.filtercol][nearPeak] == f)]) > self.singleDepthLimit:
                                        filtersBrightEnough += 1
                                if filtersBrightEnough >= self.Nfilt:
                                    if np.size(nearPeak) >= 2:
                                        gaps = t[nearPeak][1:]-np.roll(t[nearPeak],1)[1:]
                                    else:
                                        gaps = self.peakGap+1e6 
                                    if np.max(gaps) < self.peakGap:
                                        result += 1
                                        if self.uniqueBlocks:
                                            right_side = right[i]
                                        maxGap.append(np.max(gaps))
                                        Nobs.append(np.size(t))
        maxGap = np.array(maxGap)
        Nobs=np.array(Nobs)
        return {'result':result, 'maxGap':maxGap, 'Nobs':Nobs}

    @staticmethod
    def splitBySeason(dataSlice,T0):
        dates= numpy.unique(dataSlice['night'])
        gaps = dates - numpy.roll(dates,1)
        wheretosplit = numpy.where(gaps > T0)[0]
        wheretosplit= numpy.append(wheretosplit,[0,len(dates)-1])
        wheretosplit=numpy.unique(wheretosplit)
        out=[]
        for i in xrange(len(wheretosplit)-1):
            out.append(numpy.array(dates[wheretosplit[i]:wheretosplit[i+1]]))
        return out
    

    def reduceMedianMaxGap(self,data):
        """The median maximum gap near the peak of the light curve """
        result = np.median(data['maxGap'])
        if np.isnan(result):
            result = self.badval
        return result
    def reduceNsequences(self,data):
        """The number of sequences that met the requirements """
        return data['result']
    def reduceMedianNobs(self,data):
        """Median number of observations covering the entire light curve """
        result = np.median(data['Nobs'])
        if np.isnan(result):
            result = self.badval
        return result
