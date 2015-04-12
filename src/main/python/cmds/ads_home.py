cmd_home = Cmd(
    "home", home,
    "Print paths to the specified services' home directories")

def home(args):
    parser = MyArgParser(prog=cmd_home.name, description=cmd_home.description)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    print("\n".join(_collect_rel_homes(services)))