pythondir = pkgdatadir / 'ppm'

sources = [
  'accountdb.py',
  'modemproxy.py',
  'provider.py',
  'providerdb.py',
]
install_data(sources, install_dir: pythondir)

conf = configuration_data()
conf.set('VERSION', meson.project_version())
conf.set('PACKAGE', package)
conf.set('PYLIBDIR', pkgdatadir)
conf.set('GETTEXTDIR', datadir / 'locale')
conf.set('DATADIR', datadir)
conf.set('PKGDATADIR', pkgdatadir)

configure_file(
  input: '__init__.py.in',
  output: '__init__.py',
  configuration: conf,
  install_dir: pythondir,
)
