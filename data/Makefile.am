NULL = 

SUBDIRS = icons

gsettings_SCHEMAS = org.gnome.PrepaidManager.gschema.xml

@INTLTOOL_XML_NOMERGE_RULE@
@GSETTINGS_RULES@

%.gschema.xml.in: %.gschema.xml.in.in Makefile
	$(AM_V_GEN) sed -e 's^\@GETTEXT_PACKAGE\@^$(GETTEXT_PACKAGE)^g' < $< > $@

# We need to compile schemas at make time
# to run from source tree
gschemas.compiled: $(gsettings_SCHEMAS:.xml=.valid)
	$(AM_V_GEN) $(GLIB_COMPILE_SCHEMAS) --targetdir=. .

@INTLTOOL_XML_RULE@
appdatadir       = $(datadir)/appdata
appdata_in_files = prepaid-manager-applet.appdata.xml.in
appdata_DATA     = $(appdata_in_files:.xml.in=.xml)

all-local: gschemas.compiled

EXTRA_DIST = \
        org.gnome.PrepaidManager.gschema.xml.in.in \
	$(appdata_in_files) \
        $(NULL)

CLEANFILES = \
        $(gsettings_SCHEMAS) \
        gschemas.compiled    \
	$(appdata_DATA)      \
        $(NULL)

