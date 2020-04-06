conf = configuration_data()
conf.set('PYTHONDIR', pkgdatadir)
conf.set('PACKAGE', package)

configure_file(
  input: 'prepaid-manager-applet.in',
  output: 'prepaid-manager-applet',
  configuration: conf,
  install_dir: get_option('bindir')
)

sources = [package + '.py']
install_data(sources, install_dir: pkgdatadir)

subdir('ppm')
