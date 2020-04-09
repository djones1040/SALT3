import matplotlib as mpl
mpl.use('agg')
import pylab as plt
import numpy as np
from salt3.util.txtobj import txtobj
from salt3.util import getmu
from functools import partial
from scipy.stats import binned_statistic
#from salt3.pipeline.pipeline import LCFitting

__validfunctions__=dict()
def validfunction(validfunction):
    """Decorator to register a given function as a valid prior"""
    __validfunctions__[validfunction.__name__]=validfunction
    return validfunction

class ValidPlots:
	def __init__(self):
		self.validfunctions={ key: partial(__validfunctions__[key],self) \
			for key in __validfunctions__}

	def input(self,inputfile=None):
		self.inputfile = inputfile

	def output(self,outputdir=None,prefix=''):
		if not outputdir.endswith('/'):
			self.outputdir = '%s/'%outputdir
		else: self.outputdir = outputdir
		self.prefix=prefix
		
	def run(self,*args):
		validfunctions = self.validfunctions
		for k in validfunctions.keys():
			validfunctions[k](*args)


class lcfitting_validplots(ValidPlots):

	@validfunction		
	def simvfit(self):

		plt.rcParams['figure.figsize'] = (12,4)
		plt.subplots_adjust(left=None, bottom=0.2, right=None, top=None, wspace=0, hspace=0)
		fr = txtobj(self.inputfile,fitresheader=True)

		ax1,ax2,ax3 = plt.subplot(131),plt.subplot(132),plt.subplot(133)

		cbins = np.linspace(-0.3,0.3,20)
		x1bins = np.linspace(-1,1,20)
		mubins = np.linspace(-1,1,20)
		mu = fr.mB + 0.14*fr.x1 - 3.1*fr.c + 19.36
		SIM_mu = fr.SIM_mB + 0.14*fr.SIM_x1 - 3.1*fr.SIM_c + 19.36
		
		ax1.hist(fr.c-fr.SIM_c,bins=cbins)
		ax1.set_xlabel('$c - c_{\mathrm{sim}}$',fontsize=15)
		ax1.set_ylabel('N$_{\mathrm{SNe}}$',fontsize=15)
		ax2.hist(fr.x1-fr.SIM_x1,bins=x1bins)
		ax2.set_xlabel('$x_1 - x_{1,\mathrm{sim}}$',fontsize=15)
		ax3.hist(mu-SIM_mu,bins=mubins)
		ax3.set_xlabel('$\mu - \mu_{\mathrm{sim}}$',fontsize=15)

		ax2.set_ylabel([])
		ax3.yaxis.tick_right()
		
		plt.savefig('%s%s_simvfit.png'%(self.outputdir,self.prefix))

		return

	@validfunction
	def hubbleplot(self):

		plt.rcParams['figure.figsize'] = (12,4)
		plt.subplots_adjust(
			left=None, bottom=0.2, right=None, top=None, wspace=0, hspace=0)
		fr = txtobj(self.inputfile,fitresheader=True)
		ax = plt.axes()
		fr = getmu.getmu(fr)

		def errfnc(x):
			return(np.std(x)/np.sqrt(len(x)))
		
		zbins = np.logspace(np.log10(0.01),np.log10(1.0),25)
		mubins = binned_statistic(
			fr.zCMB,fr.mures,bins=zbins,statistic='mean').statistic
		mubinerr = binned_statistic(
			fr.zCMB,fr.mu,bins=zbins,statistic=errfnc).statistic
		ax.errorbar(fr.zCMB,fr.mures,yerr=fr.muerr,alpha=0.2,fmt='o')
		ax.errorbar(
			(zbins[1:]+zbins[:-1])/2.,mubins,yerr=mubinerr,fmt='o-')

		ax.axhline(0,color='k',lw=2)
		ax.set_xscale('log')
		ax.xaxis.set_major_formatter(plt.NullFormatter())
		ax.xaxis.set_minor_formatter(plt.NullFormatter())
		ax.set_ylabel('SNe',fontsize=11,labelpad=0)
		ax.set_xlim([0.01,1.0])
		ax.xaxis.set_ticks([0.01,0.02,0.05,0.1,0.2,0.3,0.5,1.0])
		ax.xaxis.set_ticklabels(['0.01','0.02','0.05','0.1','0.2','0.3','0.5','1.0'])

		ax.set_xlabel('$z_{CMB}$',fontsize=15)
		ax.set_ylabel('$\mu - \mu_{\Lambda CDM}$',fontsize=15)
		
		plt.savefig('%s%s_hubble.png'%(self.outputdir,self.prefix))

		return

class getmu_validplots(ValidPlots):

	@validfunction		
	def hubble(self):
		pass

	@validfunction
	def nuisancebias(self):
		with open(self.inputfile) as fin:
			for line in fin:
				if line.startswith('#') and 'sigint' in line:
					sigint = line.split()[3]
				elif line.startswith('#') and 'alpha0' in line:
					alpha = line.split()[3]
				elif line.startswith('#') and 'beta0' in line:
					beta = line.split()[3]
		
		fr = txtobj(self.inputfile,fitresheader=True)
		ax = plt.axes()
		ax.set_ylabel('Nuisance Parameters',fontsize=15)
		ax.xaxis.set_ticks([1,2,3])
		ax.xaxis.set_ticklabels(['alpha','beta',r'$\sigma_{\mathrm{int}}$'],rotation=30)
		
		plt.savefig('%s%s_nuisancebias.png'%(self.outputdir,self.prefix))
