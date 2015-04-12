cmd_edit = Cmd(
    "edit", edit,
    "Edit a service's ads.yml")

def edit(args):
    parser = MyArgParser(prog=cmd_edit.name, description=cmd_edit.description)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    homes = _collect_rel_homes(services)
    ymls = [os.path.join(home, "ads.yml") for home in homes]
    editor = os.environ.get('EDITOR', 'vi')
    subprocess.call([editor] + ymls)