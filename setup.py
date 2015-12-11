try:
    from setuptools import setup
except:
    import distribute_setup
    distribute_setup.use_setuptools()
    from setuptools import setup
import glob
import os

stuff = []
for f in glob.glob("*/*.py"):
    stuff.append((os.path.join("esri/toolboxes", os.path.dirname(f)),
                  [os.path.join(os.path.dirname(f),os.path.basename(f))] ))
stuff.append( ('esri/toolboxes', ["SampleTools.tbx"]))


setup(name             = "sample-gp-tools",
      version          = "0.0.1",
      description      = "",
      long_description = "",
      author           = "Esri",
      url              = "https://devtopia.esri.com/kevi5105/sample-gp-tools",
      license          = "Apache Software License",
      zip_safe         = False,
      package_dir      = {"": "."},
      packages         = ["",],
      package_data     = {"": ["*/*.py",
                               "SampleTools.tbx",
                               ] },
      data_files       = stuff,
      classifiers      = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Apache Software License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      )
