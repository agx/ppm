#                                               -*- Autoconf -*-

AC_PREREQ([2.67])
AC_INIT([prepaid-manager-applet], [0.0.3.1],
        [https://honk.sigxcpu.org/piki/projects/ppm/])
AM_INIT_AUTOMAKE([dist-xz -Wno-portability])

IT_PROG_INTLTOOL([0.35.0])

GLIB_REQUIRED=2.25.6
GTK_REQUIRED=3.0.0
PYGOBJECT_REQUIRED=3.0

PKG_CHECK_MODULES(PPM, [glib-2.0 >= $GLIB_REQUIRED
                        gtk+-3.0 >= $GTK_REQUIRED
                        pygobject-3.0 >= $PYGOBJECT_REQUIRED])

GETTEXT_PACKAGE=prepaid-manager-applet
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE,"$GETTEXT_PACKAGE", [Gettext package])
AM_GLIB_GNU_GETTEXT

GLIB_GSETTINGS

GNOME_DOC_INIT

AC_CONFIG_FILES([
Makefile
data/Makefile
data/icons/Makefile
data/icons/scalable/Makefile
data/icons/128x128/Makefile
data/icons/64x64/Makefile
data/icons/48x48/Makefile
data/icons/32x32/Makefile
po/Makefile.in
src/Makefile
src/ppm/Makefile
])
AC_OUTPUT
