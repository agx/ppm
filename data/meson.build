desktop_file = i18n.merge_file(
  input: app_id + '.desktop.in',
  output: app_id + '.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

schemas = [app_id + '.gschema.xml']
compiled = gnome.compile_schemas(
  build_by_default: true
)

install_data(
  schemas,
  install_dir: 'share/glib-2.0/schemas'
)

appstream_file = i18n.merge_file(
  input: app_id + '.appdata.xml.in',
  output: app_id + '.appdata.xml',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'appdata')
)

# Verify the AppStream file with the appropriate tool, if found.
appstream_util = find_program('appstream-util', required: false)
if appstream_util.found()
  test('Validate appstream file', appstream_util,
    args: ['validate-relax', appstream_file]
  )
endif

ppm_resources = gnome.compile_resources(
  'ppm',
  'ppm.gresources.xml',
  gresource_bundle: true,
  c_name: 'ppm',
  install: true,
  install_dir: pkgdatadir,
)

iconsdir = join_paths(get_option('datadir'), 'icons')
install_subdir('hicolor/', install_dir: iconsdir)
