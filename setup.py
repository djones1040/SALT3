from setuptools.command.test import test as TestCommand
from distutils.core import setup, Extension
import numpy.distutils.misc_util
import sys


if sys.version_info < (3,0):
	sys.exit('Sorry, Python 2 is not supported')

class SALT3Test(TestCommand):

	def run_tests(self):
		import salt3
		errno = salt3.test()
		sys.exit(errno)

AUTHOR = 'David Jones, Rick Kessler'
AUTHOR_EMAIL = 'david.jones@ucsc.edu'
VERSION = '0.1dev'
LICENSE = 'BSD'
URL = 'salt3.readthedocs.org'

#c_ext = Extension("salt3.simulation._angSep", ["salt3/simulation/_angSep.c", "salt3/simulation/angSep.c"])
#setup(
#    ext_modules=[c_ext],
#    include_dirs=numpy.distutils.misc_util.get_numpy_include_dirs(),
#)

setup(
	name='SALT3',
	version=VERSION,
	packages=['salt3','salt3.tests','salt3.data','salt3.simulation',
			  'salt3.training','salt3.util','salt3.initfiles',
			  'salt3.validation','salt3.pipeline','salt3.config'],
	cmdclass={'test': SALT3Test},
	scripts=['bin/trainsalt','bin/runpipe','salt3/validation/SynPhotPlot.py','salt3/validation/ValidateLightcurves.py','salt3/validation/ValidateModel.py','salt3/validation/ValidateSpectra.py','salt3/validation/figs/plotSALTModel.py'],
	package_data={'': ['initfiles/*.dat','initfiles/*.txt','data/kcor/*.fits','config/*conf']},
	include_package_data=True,
	author=AUTHOR,
	author_email=AUTHOR_EMAIL,
	license=LICENSE,
	long_description=open('README.md').read(),
    include_dirs=numpy.distutils.misc_util.get_numpy_include_dirs(),
	install_requires=['cython',
					  'numpy>=1.5.0',
					  'scipy>=0.9.0',
					  'extinction>=0.2.2',
					  'astropy>=0.4.0',
					  'pytest-astropy',
					  'sncosmo',
					  'astroquery',
					  'matplotlib',
					  'emcee',
					  'ipython',
					  'pandas',
					  'f90nml',
					  'iminuit',
					  'tqdm',
					  'pyyaml',
					  'pyParz'],
	)
