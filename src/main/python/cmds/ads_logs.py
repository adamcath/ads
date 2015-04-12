cmd_logs = Cmd(
    "logs", logs,
    "Tail the logs of the specified services", True)


def _collect_logs_nonempty(services, log_type):
    all_logs = []
    for s in services:
        all_logs += s.resolve_logs_relative_to_cwd(log_type)

    if len(all_logs) == 0:
        raise NotFound("No %s log files found for services %s" %
                       (log_type, str(services)))

    return all_logs


def _tail(files, project):
    project_rel_files = [
        os.path.relpath(os.path.abspath(f), project.home)
        for f in files]

    status = _shell("tail -F " + " \\\n\t".join(project_rel_files),
                    project.home)[0]
    return (status == 0 or
            status == 47)  # tail was ended by ctrl+c (Mac OS)


def _cat(files):
    return _shell("cat " + " ".join(files), os.curdir)[0] == 0


def logs(args):
    parser = MyArgParser(prog=cmd_logs.name, description=cmd_logs.description)
    sub_cmd_gp = parser.add_mutually_exclusive_group()
    sub_cmd_gp.add_argument(
        "--tail",
        action="store_true",
        help="(Default) Follow the logs with tail -f")
    sub_cmd_gp.add_argument(
        "--list",
        action="store_true",
        help="List the paths of all log files which exist "
             "(useful for pipelining)")
    sub_cmd_gp.add_argument(
        "--cat",
        action="store_true",
        help="Dump the contents of all log files to stdout")
    which_logs_gp = parser.add_mutually_exclusive_group()
    which_logs_gp.add_argument(
        "--general",
        action="store_true",
        help="(Default) Show the general logs specified by the "
             "log_paths field")
    which_logs_gp.add_argument(
        "--errors",
        action="store_true",
        help="Show the error logs specified by the err_log_paths field")
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)

    if parsed_args.errors:
        log_type = "error"
    else:
        # Default
        log_type = "general"

    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, False)
    resolved_log_paths = _collect_logs_nonempty(services, log_type)

    if parsed_args.list:
        print("\n".join(resolved_log_paths))
    elif parsed_args.cat:
        if not _cat(resolved_log_paths):
            raise InternalError("cat command failed")
    else:
        # Default
        if not _tail(resolved_log_paths, ads.project):
            raise InternalError("tail command failed")