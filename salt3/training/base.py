import os
import argparse
import configparser
import numpy as np
from salt3.config import config_rootdir
from salt3.util.specSynPhot import getColorsForSN
from argparse import SUPPRESS
import logging
log=logging.getLogger(__name__)


def expandvariablesandhomecommaseparated(paths):
	return ','.join([os.path.expanduser(os.path.expandvars(x)) for x in paths.split(',')])

class FullPaths(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		setattr(namespace, self.dest,expandvariablesandhomecommaseparated(values))

class EnvAwareArgumentParser(argparse.ArgumentParser):

	def add_argument(self,*args,**kwargs):
		if 'action' in kwargs:
			action=kwargs['action']
			
			if (action==FullPaths or action=='FullPaths') and 'default' in kwargs:
				kwargs['default']=expandvariablesandhomecommaseparated(kwargs['default'])
		return super().add_argument(*args,**kwargs)
		
class ConfigWithCommandLineOverrideParser(EnvAwareArgumentParser):
	
	def __init__(self,*args,**kwargs):
		super().__init__(*args,**kwargs)
	
	def addhelp(self):
		default_prefix='-'
		self.add_argument(
				default_prefix+'h', default_prefix*2+'help',
				action='help', default=SUPPRESS,
				help=('show this help message and exit'))

	def add_argument_with_config_default(self,config,section,*keys,**kwargs):
		"""Given a ConfigParser and a section header, scans the section for matching keys and sets them as the default value for a command line argument added to self. If a default is provided, it is used if there is no matching key in the config, otherwise this method will raise a KeyError"""
		if 'clargformat' in kwargs:
			if kwargs['clargformat'] =='prependsection':
				kwargs['clargformat']='--{section}_{key}'
		else:
			kwargs['clargformat']='--{key}'
		
		clargformat=kwargs.pop('clargformat')

		clargs=[clargformat.format(section=section,key=key) for key in keys]
		def checkforflagsinconfig():
			for key in keys:
				if key in config[section]:
					return key,config[section][key]
			raise KeyError
		try:
			includedkey,kwargs['default']=checkforflagsinconfig()
		except KeyError:
			if 'default' in kwargs:
				pass
			else:
				raise KeyError(f'Key not found in {(config)}, section {section}; valid keys include: '+', '.join(keys))
		if 'nargs' in kwargs and ((type(kwargs['nargs']) is int and kwargs['nargs']>1) or (type(kwargs['nargs'] is str and (kwargs['nargs'] in ['+','*'])))):
			if not 'type' in kwargs:
				kwargs['default']=kwargs['default'].split(',')
			else:
				kwargs['default']=list(map(kwargs['type'],kwargs['default'].split(',')))
			if type(kwargs['nargs']) is int:
				try:
					assert(len(kwargs['default'])==kwargs['nargs'])
				except:
					nargs=kwargs['nargs']
					numfound=len(kwargs['default'])
					raise ValueError(f"Incorrect number of arguments in {(config)}, section {section}, key {includedkey}, {nargs} arguments required while {numfound} were found")
		return super().add_argument(*clargs,**kwargs)
		
def boolean_string(s):
	if s not in {'False', 'True', 'false', 'true', '1', '0'}:
		raise ValueError('Not a valid boolean string')
	return (s == 'True') | (s == '1') | (s == 'true')

def nonetype_or_int(s):
	if s == 'None': return None
	else: return int(s)


class TrainSALTBase:
	def __init__(self):
		self.verbose = False
		
		
	def add_user_options(self, parser=None, usage=None, config=None):
		if parser == None:
			parser = ConfigWithCommandLineOverrideParser(usage=usage, conflict_handler="resolve",add_help=False)

		# The basics
		parser.add_argument('-v', '--verbose', action="count", dest="verbose",
							default=0,help='verbosity level')
		parser.add_argument('--debug', default=False, action="store_true",
							help='debug mode: more output and debug files')
		parser.add_argument('--clobber', default=False, action="store_true",
							help='clobber')
		parser.add_argument('-c','--configfile', default=None, type=str,
							help='configuration file')
		parser.add_argument('-s','--stage', default='all', type=str,
							help='stage - options are train and validate')

		
		# input files
		parser.add_argument_with_config_default(config,'iodata','calibrationshiftfile',  type=str,action=FullPaths,default='',
							help='file containing a list of changes to zeropoint and central wavelength of filters by survey')
		parser.add_argument_with_config_default(config,'iodata','loggingconfig','loggingconfigfile',  type=str,action=FullPaths,default='',
							help='logging config file')
		parser.add_argument_with_config_default(config,'iodata','trainingconfig','trainingconfigfile','modelconfigfile',  type=str,action=FullPaths,
							help='Configuration file describing the construction of the model')
		parser.add_argument_with_config_default(config,'iodata','snlists','snlistfiles',  type=str,action=FullPaths,
							help="""list of SNANA-formatted SN data files, including both photometry and spectroscopy. Can be multiple comma-separated lists. (default=%(default)s)""")
		parser.add_argument_with_config_default(config,'iodata','snparlist', 'snparlistfile', type=str,action=FullPaths,
							help="""optional list of initial SN parameters.  Needs columns SNID, zHelio, x0, x1, c""")
		parser.add_argument_with_config_default(config,'iodata','specrecallist','specrecallistfile',  type=str,action=FullPaths,
							help="""optional list giving number of spectral recalibration params.  Needs columns SNID, N, phase, ncalib where N is the spectrum number for a given SN, starting at 1""")
		parser.add_argument_with_config_default(config,'iodata','tmaxlist','tmaxlistfile',  type=str,action=FullPaths,
							help="""optional space-delimited list with SN ID, tmax, tmaxerr (default=%(default)s)""")
	
		#output files
		parser.add_argument_with_config_default(config,'iodata','outputdir',  type=str,action=FullPaths,
							help="""data directory for spectroscopy, format should be ASCII 
							with columns wavelength, flux, fluxerr (optional) (default=%(default)s)""")
		parser.add_argument_with_config_default(config,'iodata','yamloutputfile', default='/dev/null',type=str,action=FullPaths,
							help='File to which to output a summary of the fitting process')
		
		#options to configure cuts
		parser.add_argument_with_config_default(config,'iodata','dospec',  type=boolean_string,
							help="""if set, look for spectra in the snlist files (default=%(default)s)""")
		parser.add_argument_with_config_default(config,'iodata','maxsn',  type=nonetype_or_int,
							help="""sets maximum number of SNe to fit for debugging (default=%(default)s)""")
		parser.add_argument_with_config_default(config,'iodata','keeponlyspec',  type=boolean_string,
							help="""if set, only train on SNe with spectra (default=%(default)s)""")
		parser.add_argument_with_config_default(config,'iodata','filter_mass_tolerance',  type=float,
							help='Mass of filter transmission allowed outside of model wavelength range (default=%(default)s)')

		#Initialize from SALT2.4		
		parser.add_argument_with_config_default(config,'iodata','initsalt2model',  type=boolean_string,
							help="""If true, initialize model parameters from prior SALT2 model""")
		parser.add_argument_with_config_default(config,'iodata','initsalt2var',  type=boolean_string,
							help="""If true, initialize model uncertainty parameters from prior SALT2 model""")
		#Initialize from user defined files				
		parser.add_argument_with_config_default(config,'iodata','initm0modelfile',  type=str,action=FullPaths,
							help="""initial M0 model to begin training, ASCII with columns
							phase, wavelength, flux (default=%(default)s)""")
		parser.add_argument_with_config_default(config,'iodata','initm1modelfile',  type=str,action=FullPaths,
							help="""initial M1 model with x1=1 to begin training, ASCII with columns
							phase, wavelength, flux (default=%(default)s)""")
		#Choose B filter definition
		parser.add_argument_with_config_default(config,'iodata','initbfilt',  type=str,action=FullPaths,
							help="""initial B-filter to get the normalization of the initial model (default=%(default)s)""")
							
		parser.add_argument_with_config_default(config,'iodata','resume_from_outputdir',  type=str,action=FullPaths,
							help='if set, initialize using output parameters from previous run. If directory, initialize using ouptut parameters from specified directory')
		parser.add_argument_with_config_default(config,'iodata','fix_salt2modelpars',  type=boolean_string,
							help="""if set, fix M0/M1 for wavelength/phase range of original SALT2 model (default=%(default)s)""")


		parser.add_argument_with_config_default(config,'trainparams','do_mcmc',  type=boolean_string,
							help='do MCMC fitting (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','do_gaussnewton',  type=boolean_string,
							help='do Gauss-Newton least squares (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','gaussnewton_maxiter',  type=int,
							help='maximum iterations for Gauss-Newton (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','regularize',  type=boolean_string,
							help='turn on regularization if set (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','fitsalt2',  type=boolean_string,
							help='fit SALT2 as a validation check (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','n_repeat',  type=int,
							help='repeat mcmc and/or gauss newton n times (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','fit_model_err',  type=boolean_string,
							help='fit for model error if set (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','fit_cdisp_only',  type=boolean_string,
							help='fit for color dispersion component of model error if set (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','fit_tpkoff',  type=boolean_string,
							help='fit for time of max in B-band if set (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainparams','fitting_sequence',  type=str,
							help="Order in which parameters are fit, 'default' or empty string does the standard approach, otherwise should be comma-separated list with any of the following: all, pcaparams, color, colorlaw, spectralrecalibration, sn, tpk (default=%(default)s)")

		# mcmc parameters
		parser.add_argument_with_config_default(config,'mcmcparams','n_steps_mcmc',  type=int,
							help='number of accepted MCMC steps (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','n_burnin_mcmc',  type=int,
							help='number of burn-in MCMC steps	(default=%(default)s)')


		# survey definitions
		self.surveylist = [section.replace('survey_','') for section in config.sections() if section.startswith('survey_')]
		for survey in self.surveylist:
			
			parser.add_argument_with_config_default(config,f'survey_{survey}',"kcorfile" ,type=str,clargformat=f"--{survey}" +"_{key}",
								help="kcor file for survey %s"%survey)
			parser.add_argument_with_config_default(config,f'survey_{survey}',"subsurveylist" ,type=str,clargformat=f"--{survey}" +"_{key}",
								help="comma-separated list of subsurveys for survey %s"%survey)

		return parser


	def add_training_options(self, parser=None, usage=None, config=None):
		if parser == None:
			parser = ConfigWithCommandLineOverrideParser(usage=usage, conflict_handler="resolve")

		# training params
		parser.add_argument_with_config_default(config,'trainingparams','specrecal',  type=int,
							help='number of parameters defining the spectral recalibration (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','n_processes',  type=int,
							help='number of processes to use in calculating chi2 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','estimate_tpk',  type=boolean_string,
							help='if set, estimate time of max with quick least squares fitting (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','fix_t0',  type=boolean_string,
							help='if set, don\'t allow time of max to float (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','regulargradientphase',  type=float,
							help='Weighting of phase gradient chi^2 regularization during training of model parameters (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','regulargradientwave',  type=float,
							help='Weighting of wave gradient chi^2 regularization during training of model parameters (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','regulardyad',  type=float,
							help='Weighting of dyadic chi^2 regularization during training of model parameters (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','m1regularization',  type=float,
							help='Scales regularization weighting of M1 component relative to M0 weighting (>1 increases smoothing of M1)  (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','spec_chi2_scaling',  type=float,
							help='scaling of spectral chi^2 so it doesn\'t dominate the total chi^2 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','n_min_specrecal',  type=int,
							help='Minimum order of spectral recalibration polynomials (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','specrange_wavescale_specrecal',  type=float,
							help='Wavelength scale (in angstroms) for determining additional orders of spectral recalibration from wavelength range of spectrum (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','n_specrecal_per_lightcurve',  type=float,
							help='Number of additional spectral recalibration orders per lightcurve (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','regularizationScaleMethod',  type=str,
							help='Choose how scale for regularization is calculated (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','binspec',  type=boolean_string,
							help='bin the spectra if set (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','binspecres',  type=int,
							help='binning resolution (default=%(default)s)')
		
   		#neff parameters
		parser.add_argument_with_config_default(config,'trainingparams','wavesmoothingneff',  type=float,
							help='Smooth effective # of spectral points along wave axis (in units of waveoutres) (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','phasesmoothingneff',  type=float,
							help='Smooth effective # of spectral points along phase axis (in units of phaseoutres) (default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','nefffloor',  type=float,
							help='Minimum number of effective points (has to be > 0 to prevent divide by zero errors).(default=%(default)s)')
		parser.add_argument_with_config_default(config,'trainingparams','neffmax',  type=float,
							help='Threshold for spectral coverage at which regularization will be turned off (default=%(default)s)')

		# training model parameters
		parser.add_argument_with_config_default(config,'modelparams','waverange', type=int, nargs=2,
							help='wavelength range over which the model is defined (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','colorwaverange',  type=int, nargs=2,
							help='wavelength range over which the color law is fit to data (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','interpfunc',  type=str,
							help='function to interpolate between control points in the fitting (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','errinterporder',  type=int,
							help='for model uncertainty splines/polynomial funcs, order of the function (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','interporder',  type=int,
							help='for model splines/polynomial funcs, order of the function (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','wavesplineres',  type=float,
							help='number of angstroms between each wavelength spline knot (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','phasesplineres',  type=float,
							help='number of angstroms between each phase spline knot (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','waveinterpres',  type=float,
							help='wavelength resolution in angstroms, used for internal interpolation (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','phaseinterpres',  type=float,
							help='phase resolution in angstroms, used for internal interpolation (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','waveoutres',  type=float,
							help='wavelength resolution in angstroms of the output file (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','phaseoutres',  type=float,
							help='phase resolution in angstroms of the output file (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','phaserange', type=int, nargs=2,
							help='phase range over which model is trained (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','n_components',  type=int,
							help='number of principal components of the SALT model to fit for (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','n_colorpars',  type=int,
							help='number of degrees of the phase-independent color law polynomial (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','n_colorscatpars',  type=int,
							help='number of parameters in the broadband scatter model (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','error_snake_phase_binsize',  type=float,
							help='number of days over which to compute scaling of error model (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','error_snake_wave_binsize',  type=float,
							help='number of angstroms over which to compute scaling of error model (default=%(default)s)')
		parser.add_argument_with_config_default(config,'modelparams','use_snpca_knots',  type=boolean_string,
							help='if set, define model on SNPCA knots (default=%(default)s)')
		
		
		# mcmc parameters
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_magscale_M0',  type=float,
							help='initial MCMC step size for M0, in mag	 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_magadd_M0',  type=float,
							help='initial MCMC step size for M0, in mag	 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_magscale_err',  type=float,
							help='initial MCMC step size for the model err spline knots, in mag  (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_errcorr',  type=float,
							help='initial MCMC step size for the correlation between model error terms, in mag  (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_magscale_M1',  type=float,
							help='initial MCMC step size for M1, in mag - need both mag and flux steps because M1 can be negative (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_magadd_M1',  type=float,
							help='initial MCMC step size for M1, in flux - need both mag and flux steps because M1 can be negative (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_cl',  type=float,
							help='initial MCMC step size for color law	(default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_magscale_clscat',  type=float,
							help='initial MCMC step size for color law	(default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_specrecal',  type=float,
							help='initial MCMC step size for spec recal. params	 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_x0',  type=float,
							help='initial MCMC step size for x0, in mag	 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_x1',  type=float,
							help='initial MCMC step size for x1	 (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_c',  type=float,
							help='initial MCMC step size for c	(default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','stepsize_tpk',  type=float,
							help='initial MCMC step size for tpk  (default=%(default)s)')

		# adaptive MCMC parameters
		parser.add_argument_with_config_default(config,'mcmcparams','nsteps_before_adaptive',  type=float,
							help='number of steps before starting adaptive step sizes (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','nsteps_adaptive_memory',  type=float,
							help='number of steps to use to estimate adaptive steps (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','modelpar_snpar_tradeoff_nstep',  type=float,
							help='number of steps when trading between adjusting model params and SN params (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','nsteps_before_modelpar_tradeoff',  type=float,
							help='number of steps when trading between adjusting model params and SN params (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','nsteps_between_lsqfit',  type=float,
							help='every x number of steps, adjust the SN params via least squares fitting (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','use_lsqfit',  type=boolean_string,
							help='if set, periodically adjust the SN params via least squares fitting (default=%(default)s)')
		parser.add_argument_with_config_default(config,'mcmcparams','adaptive_sigma_opt_scale',  type=float,
							help='scaling the adaptive step sizes (default=%(default)s)')
		
				

		# priors
		for prior,val in config.items('priors'):
			parser.add_argument_with_config_default(config,'priors',prior ,type=float,clargformat="--prior_{key}",
								help=f"prior on {prior}")

		# bounds
		for bound,val in config.items('bounds'):
			parser.add_argument_with_config_default(config,'bounds', bound, type=float,nargs=3,clargformat="--bound_{key}",
								help="bound on %s"%bound)
		#import pdb; pdb.set_trace()

		return parser

	def get_saltkw(self,phaseknotloc,waveknotloc,errphaseknotloc,errwaveknotloc):


		saltfitkwargs = {'m1regularization':self.options.m1regularization,'bsorder':self.options.interporder,'errbsorder':self.options.errinterporder,
						 'waveSmoothingNeff':self.options.wavesmoothingneff,'phaseSmoothingNeff':self.options.phasesmoothingneff,
						 'neffFloor':self.options.nefffloor, 'neffMax':self.options.neffmax,
						 'specrecal':self.options.specrecal, 'regularizationScaleMethod':self.options.regularizationScaleMethod,
						 'phaseinterpres':self.options.phaseinterpres,'waveinterpres':self.options.waveinterpres,
						 'phaseknotloc':phaseknotloc,'waveknotloc':waveknotloc,
						 'errphaseknotloc':errphaseknotloc,'errwaveknotloc':errwaveknotloc,
						 'phaserange':self.options.phaserange,
						 'waverange':self.options.waverange,'phaseres':self.options.phasesplineres,
						 'waveres':self.options.wavesplineres,'phaseoutres':self.options.phaseoutres,
						 'waveoutres':self.options.waveoutres,
						 'colorwaverange':self.options.colorwaverange,
						 'kcordict':self.kcordict,'initm0modelfile':self.options.initm0modelfile,
						 'initbfilt':self.options.initbfilt,'regulargradientphase':self.options.regulargradientphase,
						 'regulargradientwave':self.options.regulargradientwave,'regulardyad':self.options.regulardyad,
						 'filter_mass_tolerance':self.options.filter_mass_tolerance,
						 'specrange_wavescale_specrecal':self.options.specrange_wavescale_specrecal,
						 'n_components':self.options.n_components,'n_colorpars':self.options.n_colorpars,
						 'n_colorscatpars':self.options.n_colorscatpars,
						 'nsteps_before_adaptive':self.options.nsteps_before_adaptive,
						 'nsteps_adaptive_memory':self.options.nsteps_adaptive_memory,
						 'adaptive_sigma_opt_scale':self.options.adaptive_sigma_opt_scale,
						 'stepsize_magscale_M0':self.options.stepsize_magscale_M0,
						 'stepsize_magadd_M0':self.options.stepsize_magadd_M0,
						 'stepsize_magscale_err':self.options.stepsize_magscale_err,
						 'stepsize_errcorr':self.options.stepsize_errcorr,
						 'stepsize_magscale_M1':self.options.stepsize_magscale_M1,
						 'stepsize_magadd_M1':self.options.stepsize_magadd_M1,
						 'stepsize_cl':self.options.stepsize_cl,
						 'stepsize_magscale_clscat':self.options.stepsize_magscale_clscat,
						 'stepsize_specrecal':self.options.stepsize_specrecal,
						 'stepsize_x0':self.options.stepsize_x0,
						 'stepsize_x1':self.options.stepsize_x1,
						 'stepsize_c':self.options.stepsize_c,
						 'stepsize_tpk':self.options.stepsize_tpk,
						 'fix_t0':self.options.fix_t0,
						 'nsteps_before_modelpar_tradeoff':self.options.nsteps_before_modelpar_tradeoff,
						 'modelpar_snpar_tradeoff_nstep':self.options.modelpar_snpar_tradeoff_nstep,
						 'nsteps_between_lsqfit':self.options.nsteps_between_lsqfit,
						 'use_lsqfit':self.options.use_lsqfit,
						 'regularize':self.options.regularize,
						 'outputdir':self.options.outputdir,
						 'fit_model_err':self.options.fit_model_err,
						 'fit_cdisp_only':self.options.fit_cdisp_only,
						 'fitTpkOff':self.options.fit_tpkoff,
						 'spec_chi2_scaling':self.options.spec_chi2_scaling}
		
		for k in self.options.__dict__.keys():
			if k.startswith('prior') or k.startswith('bound'):
				saltfitkwargs[k] = self.options.__dict__[k]
		return saltfitkwargs

	def mkcuts(self,datadict,KeepOnlySpec=False):

		# Eliminate all data outside wave/phase range
		numSpecElimmed,numSpec=0,0
		numPhotElimmed,numPhot=0,0
		numSpecPoints=0
		failedlist = []
		log.info('hack! no spec color cut')
		#log.info('hack!  no cuts at all')
		#return datadict
		for sn in list(datadict.keys()):
			photdata = datadict[sn]['photdata']
			specdata = datadict[sn]['specdata']
			z = datadict[sn]['zHelio']

			# cuts
			# 4 epochs at -10 < phase < 35
			# 1 measurement near peak
			# 1 measurement at 5 < t < 20
			# 2 measurements at -8 < t < 10
			phase = (photdata['mjd'] - datadict[sn]['tpk'])/(1+z)
			iEpochsCut = np.where((phase > -10) & (phase < 35))[0]
			iPkCut = np.where((phase > -10) & (phase < 5))[0]
			iShapeCut = np.where((phase > 5) & (phase < 20))[0]
			iColorCut = np.where((phase > -8) & (phase < 10))[0]
			NFiltColorCut = len(np.unique(photdata['filt'][iColorCut]))
			iPreMaxCut = len(np.unique(photdata['filt'][np.where((phase > -10) & (phase < -2))[0]]))
			medSNR = np.median(photdata['fluxcal'][(phase > -10) & (phase < 10)]/photdata['fluxcalerr'][(phase > -10) & (phase < 10)])
			hasvalidfitprob=datadict[sn]['fitprob']!=-99
			iFitprob = (datadict[sn]['fitprob'] >= 1e-4)
			if not iFitprob:
				log.debug(f'SN {sn} failing fitprob cut!')
			if not hasvalidfitprob:
				log.warning(f'SN {sn} does not have a valid fitprob, including in sample')
				iFitprob=True
			if len(iEpochsCut) < 4 or not len(iPkCut) or not len(iShapeCut) or NFiltColorCut < 2 or not iFitprob: # or iPreMaxCut < 2 or medSNR < 10:
				datadict.pop(sn)
				failedlist += [sn]
				log.debug('SN %s fails cuts'%sn)
				log.debug('%i epochs, %i epochs near peak, %i epochs post-peak, %i filters near peak'%(
						len(iEpochsCut),len(iPkCut),len(iShapeCut),NFiltColorCut))
				continue

			#Remove spectra outside phase range
			for k in list(specdata.keys()):
				# remove spectra with bad colors
				# colordiffs = getColorsForSN(
				#	specdata[k],photdata,self.kcordict,datadict[sn]['survey'])
				
				#if colordiffs is None or len(colordiffs[np.abs(colordiffs) > 0.1]):
				#	specdata.pop(k)
				#	numSpecElimmed += 1
				if ((specdata[k]['tobs'])/(1+z)<self.options.phaserange[0]) or \
				   ((specdata[k]['tobs'])/(1+z)>self.options.phaserange[1]-3):
					specdata.pop(k)
					numSpecElimmed+=1
				elif specdata[k]['mjd'] < np.min(photdata['mjd']) or \
					 specdata[k]['mjd'] > np.max(photdata['mjd']):
					specdata.pop(k)
					numSpecElimmed+=1
				else:
					numSpec+=1
					numSpecPoints+=((specdata[k]['wavelength']/(1+z)>self.options.waverange[0]) &
									(specdata[k]['wavelength']/(1+z)<self.options.waverange[1])).sum()
			if KeepOnlySpec and not len(specdata.keys()):
				datadict.pop(sn)
				continue
			
			#Remove photometric data outside phase range
			phase=(photdata['tobs'])/(1+z)
			def checkFilterMass(flt):
				survey = datadict[sn]['survey']
				filtwave = self.kcordict[survey][flt]['filtwave']
				try:
					filttrans = self.kcordict[survey][flt]['filttrans']
				except:
					raise RuntimeError('filter %s not found in kcor file for SN %s'%(flt,sn))
					
				#Check how much mass of the filter is inside the wavelength range
				filtRange=(filtwave/(1+z) > self.options.waverange[0]) & \
						   (filtwave/(1+z) < self.options.waverange[1])
				return np.trapz((filttrans*filtwave/(1+z))[filtRange],
								filtwave[filtRange]/(1+z))/np.trapz(
									filttrans*filtwave/(1+z),
									filtwave/(1+z)) > 1-self.options.filter_mass_tolerance

			filterInBounds=np.vectorize(checkFilterMass)(photdata['filt'])
			phaseInBounds=(phase>self.options.phaserange[0]) & (phase<self.options.phaserange[1])
			keepPhot=filterInBounds&phaseInBounds
			numPhotElimmed+=(~keepPhot).sum()
			numPhot+=keepPhot.sum()
			datadict[sn]['photdata'] ={key:photdata[key][keepPhot] for key in photdata}

		#if self.options.maxsn is not None:
		#	surveys = np.unique([datadict[k]['survey'].split('(')[0] for k in datadict.keys()])
		#	for s in surveys:
		#		count = 0
		#		for i,sn in enumerate(list(datadict.keys())):
		#			if datadict[sn]['survey'].split('(')[0] != s: continue
		#			if count >= self.options.maxsn/len(surveys):
		#				datadict.pop(sn)
		#			count += 1

		log.info('{} spectra and {} photometric observations removed for being outside phase range'.format(numSpecElimmed,numPhotElimmed))
		log.info('{} spectra and {} photometric observations remaining'.format(numSpec,numPhot))
		log.info('{} total spectroscopic data points'.format(numSpecPoints))
		log.info('Total number of supernovae: {}'.format(len(datadict)))

		#surveys,redshifts = [],[]
		#for k in datadict.keys():
		#	surveys += [datadict[k]['survey']]
		#	redshifts += [datadict[k]['zHelio']]
		#surveys = np.array(surveys)
		#import pdb; pdb.set_trace()
		return datadict
