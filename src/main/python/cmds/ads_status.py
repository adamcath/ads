cmd_status = Cmd(
    "status", status,
    "Print status of the specified services", True)


def _status(service, verbose):
    if not service.status_cmd:
        running = False
        msg = "status command not defined"
    else:
        if verbose:
            debug("Checking if %s is running" % service.name)
        running = _shell(service.status_cmd,
                         service.home,
                         verbose and STREAM or NULL)[0] == 0
        msg = running and "ok" or "not running"
    info(service.name + ": " + msg)
    return running


def status(args):
    parser = MyArgParser(prog=cmd_status.name,
                         description=cmd_status.description)
    _add_verbose_arg(parser)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, False)
    if not all(map(lambda sp: _status(sp, parsed_args.verbose), services)):
        raise SomeDown()
