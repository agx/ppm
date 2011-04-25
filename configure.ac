#                                               -*- Autoconf -*-

AC_PREREQ([2.67])
AC_INIT([prepaid-manager-applet], [0.0.0],
        [http://honk.sigxcpu.org/projects/prepaid-manager.py])
AM_INIT_AUTOMAKE([-Wno-portability])

IT_PROG_INTLTOOL([0.35.0])

GETTEXT_PACKAGE=prepaid-manager-applet
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE,"$GETTEXT_PACKAGE", [Gettext package])
AM_GLIB_GNU_GETTEXT

GLIB_GSETTINGS

GNOME_DOC_INIT

AC_CONFIG_FILES([
Makefile
data/Makefile
po/Makefile.in
src/Makefile
src/ppm/Makefile
])
AC_OUTPUT
