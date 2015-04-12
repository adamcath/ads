cmd_bounce = Cmd(
    "bounce", bounce,
    "Stop and restart the specified services", False,
    ["restart"])


def bounce(args):
    parser = MyArgParser(prog=cmd_bounce.name,
                         description=cmd_bounce.description)
    _add_verbose_arg(parser)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    all_stopped = all(
        map(lambda sp: _down(sp, parsed_args.verbose), services))
    all_started = all(
        map(lambda sp: _up(sp, parsed_args.verbose), services))
    if not all_stopped:
        raise StopFailed("One or more services failed to stop")
    if not all_started:
        raise StartFailed("One or more services failed to restart")
