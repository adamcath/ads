cmd_down = Cmd(
    "down", down,
    "Ensure the specified services are not running", True,
    ["stop", "kill"])


def _down(service, verbose):
    # Is it running?
    if not service.status_cmd:
        error("Status command not defined for " + service.name +
              "; can't tell if it's already stopped")
        return False
    if verbose:
        debug("Checking if %s is running" % service.name)
    if not _is_running(service, verbose):
        info(service.name + " is already stopped")
        return True

    # Is stop defined?
    if not service.stop_cmd:
        error("Stop command not defined for " + service.name)
        return False

    # Do it
    info("Stopping %s" % service.name)
    (status, out) = _shell(service.stop_cmd, service.home,
                           verbose and STREAM or BUFFER)
    if status == 0:
        if verbose:
            debug("Stopped " + service.name)
        return True
    else:
        error("Failed to stop " + service.name)
        if not verbose:
            sys.stderr.write(out)
            error(separator())
        else:
            # Output was already streamed
            pass
        return False


def down(args):
    parser = MyArgParser(prog=cmd_down.name, description=cmd_down.description)
    _add_verbose_arg(parser)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    if not all(map(lambda sp: _down(sp, parsed_args.verbose), services)):
        raise StopFailed("One or more services failed to stop")

