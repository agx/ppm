project('ppm',
  version: '0.0.7',
  meson_version: '>= 0.49.0',
)

package = 'prepaid-manager-applet'
prefix = get_option('prefix')
datadir = join_paths(prefix, get_option('datadir'))
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), package)

gnome = import('gnome')
i18n = import('i18n')

gio_dep = dependency('gio-2.0', version: '>=2.25.6')
gtk_dep = dependency('gtk+-3.0', version: '>=3.0.0')
pygobject_dep = dependency('pygobject-3.0', version: '>=3.0')

subdir('data')
subdir('src')
subdir('po')

