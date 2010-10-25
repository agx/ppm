NULL =

pythondir = $(pkgdatadir)/ppm/
python_DATA_IN = __init__.py.in
python_DATA = \
		__init__.py	\
		modemproxy.py	\
		provider.py	\
		providerdb.py	\
		$(NULL)


EXTRA_DIST = $(python_DATA) $(python_DATA_IN)

%.py: $(srcdir)/%.py.in
	sed -e "s,::PACKAGE::,$(PACKAGE)," \
	  -e "s,::PYLIBDIR::,$(pkgdatadir)," \
	  -e "s,::GETTEXTDIR::,$(datadir)/locale," \
	  -e "s,::DATADIR::,$(datadir)," \
	  -e "s,::PKGDATADIR::,$(pkgdatadir)," \
	  < $< > $@

CLEANFILES = *.pyc
