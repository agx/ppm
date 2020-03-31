desktop_file = i18n.merge_file(
  input: 'prepaid-manager-applet.desktop.in',
  output: 'prepaid-manager-applet.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

conf = configuration_data()
conf.set('PYTHONDIR', pkgdatadir)
conf.set('PACKAGE', package)

configure_file(
  input: 'prepaid-manager-applet.in',
  output: 'prepaid-manager-applet',
  configuration: conf,
  install_dir: get_option('bindir')
)

sources = [
  package + '.py',
  'ppm.ui',
  'ppm-provider-assistant.ui',
]
install_data(sources, install_dir: pkgdatadir)

subdir('ppm')
