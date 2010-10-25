SUBDIRS = ppm

bin_SCRIPTS_IN = prepaid-manager-applet.in
bin_SCRIPTS = prepaid-manager-applet

desktopdir       = $(datadir)/applications
desktop_in_files = prepaid-manager-applet.desktop.in
desktop_DATA     = $(desktop_in_files:.desktop.in=.desktop)

pythondir = $(pkgdatadir)
python_DATA = $(PACKAGE).py

EXTRA_DIST = $(python_DATA) $(desktop_in_files) $(ui_DATA)

@INTLTOOL_DESKTOP_RULE@

uidir = $(pkgdatadir)
ui_DATA = $(wildcard $(srcdir)/*.ui)

$(PACKAGE): $(srcdir)/$(PACKAGE).in
	sed -e "s,::PACKAGE::,$(PACKAGE)," -e "s,::PYTHONDIR::,$(pkgdatadir)," < $< > $@

CLEANFILES = *.pyc $(desktop_DATA) $(bin_SCRIPTS)
