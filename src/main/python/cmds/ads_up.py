import argparse
from ads_helpers import *

cmd_up = Cmd(
    "up", up,
    "Ensure the specified services are running", True,
    ["start", "run"])


def _up(service, verbose):
    # Is it running?
    if not service.status_cmd:
        error("Status command not defined for " + service.name +
              "; can't tell if it's already running")
        return False
    if verbose:
        debug("Checking if %s is already running" % service.name)
    if _is_running(service, verbose):
        info(service.name + " is already running")
        return True

    # Is start defined?
    if not service.start_cmd:
        error("Start command not defined for " + service.name)
        return False

    # Do it
    info("Starting " + service.name)
    (status, out) = _shell(service.start_cmd, service.home,
                           verbose and STREAM or BUFFER)
    if status == 0:
        if verbose:
            debug("Started " + service.name)
        return True
    else:
        error("Failed to start " + service.name)
        if not verbose:
            sys.stderr.write(out)
            error(separator())
        else:
            # Output was already streamed
            pass
        return False


def up(args):
    parser = MyArgParser(prog=cmd_up.name, description=cmd_up.description)
    _add_verbose_arg(parser)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    if len(services) > 1:
        info("Starting " + str(services))
    if not all(map(lambda sp: _up(sp, parsed_args.verbose), services)):
        raise StartFailed("One or more services failed to start")

