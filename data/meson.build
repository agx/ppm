desktop_file = i18n.merge_file(
  input: 'prepaid-manager-applet.desktop.in',
  output: 'prepaid-manager-applet.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

schemas = ['org.gnome.PrepaidManager.gschema.xml']
compiled = gnome.compile_schemas(
  build_by_default: true
)

install_data(
  schemas,
  install_dir: 'share/glib-2.0/schemas'
)

appstream_file = i18n.merge_file(
  input: 'prepaid-manager-applet.appdata.xml.in',
  output: 'prepaid-manager-applet.appdata.xml',
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

iconsdir = join_paths(get_option('datadir'), 'icons', 'hicolor')
foreach size: ['scalable', '128x128', '64x64', '48x48', '32x32']
  install_subdir('icons/' + size, install_dir: iconsdir)
endforeach
