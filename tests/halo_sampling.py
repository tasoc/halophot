import numpy as np
import matplotlib.pyplot as plt
from astropy.table import Table
import scipy.optimize as optimize
import fitsio
from time import time as clock
from SuzPyUtils.norm import medsig
from psf_sim import *
from k2sc.cdpp import cdpp

import matplotlib as mpl

mpl.style.use('seaborn-colorblind')

#To make sure we have always the same matplotlib settings
#(the ones in comments are the ipython notebook settings)

mpl.rcParams['figure.figsize']=(8.0,6.0)    #(6.0,4.0)
mpl.rcParams['font.size']=18               #10 
mpl.rcParams['savefig.dpi']= 200             #72 
mpl.rcParams['axes.labelsize'] = 16
mpl.rcParams['axes.labelsize'] = 16
mpl.rcParams['xtick.labelsize'] = 12
mpl.rcParams['ytick.labelsize'] = 12


fname = '../EPIC_211309989_mast.fits' # point this path to your favourite K2SC light curve
lc = Table.read(fname)

x, y = lc['x'][150:1550], lc['y'][150:1550] # copy in the xy variations from real data 

ncad = np.size(x)

'''------------------------
Generate a toy light curve
------------------------'''

t = np.linspace(0,100,ncad)

f = 20*np.ones(ncad) + np.sin(t/6.) # make this whatever function you like! 
f[400:500] *= 0.990 # toy transit


'''------------------------
Define a PSF and aperture
------------------------'''

samplings = np.array([75,125])
samplings = range(10,400,10)


sigs_raw = 1.*np.zeros_like(samplings)
sigs_1 = 1.*np.zeros_like(samplings)
sigs_2 = 1.*np.zeros_like(samplings)
times_1 = 1.*np.zeros_like(samplings)
times_2 = 1.*np.zeros_like(samplings)

width = 6.

nx, ny = 20, 20
npix = nx*ny
pixels = np.zeros((nx,ny))
psf = gaussian_psf(pixels,x[0],y[0],width)
tpf = np.zeros((nx,ny,ncad))
sensitivity = 1-0.1*np.random.rand(nx,ny)
white = 0

'''------------------------
Simulate data
------------------------'''

for j in range(ncad):
    tpf[:,:,j] = f[j]*gaussian_psf(pixels,x[j],y[j],width)*sensitivity + np.random.randn(nx,ny)*white

pixelvectors_all = np.reshape(tpf,(npix,ncad))

all_inds = range(npix)

start = clock()

for jj,sampling in enumerate(samplings):
	print 'Taking',sampling,'pixels'

	pixelvectors = pixelvectors_all[np.random.choice(all_inds,sampling)]

	'''------------------------
	Define objectives
	------------------------'''


	def obj_1(weights):
	    flux = np.dot(weights.T,pixelvectors)
	    return diff_1(flux)/np.nanmedian(flux)

	def obj_2(weights):
	#     return np.dot(w.T,sigma_flux,w)
	    flux = np.dot(weights.T,pixelvectors)
	    return diff_2(flux)/np.nanmedian(flux)

	'''------------------------
	Reconstruct lightcurves
	------------------------'''

	cons = ({'type': 'eq', 'fun': lambda z: z.sum() - 1.})
	bounds = (sampling)*((0,1),)

	w_init = np.random.rand(sampling)
	w_init /= np.sum(w_init)
	# w_init = np.ones(180)/180.

	tic = clock()
	    
	res1 = optimize.minimize(obj_1, w_init, method='SLSQP', constraints=cons, bounds = bounds,
	                        options={'disp': False})
	xbest_1 = res1['x']

	toc = clock()

	res2 = optimize.minimize(obj_2, xbest_1, method='SLSQP', constraints=cons, bounds = bounds,
	                        options={'disp': False})
	xbest_2 = res2['x']
	toc2 = clock()

	print 'Time taken for TV1:',(toc-tic)
	print 'Time taken for TV2:', (toc2-toc)

	lc_opt_1 = np.dot(xbest_1.T,pixelvectors)
	lc_opt_2 = np.dot(xbest_2.T,pixelvectors)

	raw_lc = np.sum(pixelvectors,axis=0)

	raw_lc /= np.nanmedian(raw_lc)
	lc_opt_1 /= np.nanmedian(lc_opt_1)
	lc_opt_2 /= np.nanmedian(lc_opt_2)

	ssr = cdpp(t,raw_lc-f/np.nanmedian(f)+1)
	ss1 = cdpp(t,lc_opt_1-f/np.nanmedian(f)+1)
	ss2 = cdpp(t,lc_opt_2-f/np.nanmedian(f)+1)

	sigs_raw[jj] = ssr
	sigs_1[jj] = ss1
	sigs_2[jj] = ss2 
	times_1[jj] = toc-tic
	times_2[jj] = toc2-toc

finish = clock()
print 'Done'
print 'Time elapsed:',finish-start

ticks = np.unique(samplings[samplings%5==0])

plt.figure(0)
plt.clf()

plt.plot(samplings,sigs_raw,'.-',label='Raw')
plt.plot(samplings,sigs_1,'.-',label='TV1')
plt.plot(samplings,sigs_2,'.-',label='TV2')
plt.ylabel('CDPP (ppm)')
plt.xlabel('Subsampling')
plt.yscale('log')
plt.title(r'Precision of TV: Gaussian PSF, $\sigma$=%.1f' % width)
plt.xticks(ticks)
plt.legend()
plt.savefig('samplings.png')

