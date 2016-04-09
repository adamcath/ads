import sys


class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def debug(msg):
    print(colors.OKBLUE + msg + colors.ENDC)
    sys.stdout.flush()


def info(msg):
    print(colors.OKGREEN + "--- " + msg + colors.ENDC)
    sys.stdout.flush()


def error(msg):
    sys.stderr.write(colors.FAIL + "!!! " + msg + "\n" + colors.ENDC)
    sys.stderr.flush()


def separator():
    return "--------------------------------"


try:
    import yaml
except ImportError:
    error(
        "ads requires the python package 'pyyaml'.\n"
        "Please install it with 'pip install pyyaml' or 'easy_install pyyaml'\n"
        "(disregard the message about 'forcing --no-libyaml')")
    sys.exit(1)

import os
import tempfile
import subprocess
import argparse
import glob
import time
from collections import OrderedDict


##############################################
# Treelisting
##############################################

class Treelisting:
    def __init__(self, sections=None):
        self.sections = sections or []

    def with_section(self, heading, listing_dict, empty_msg=None):
        self.sections.append((heading, listing_dict, empty_msg))
        return self

    def pretty_print(self):
        all_keys = [
            k
            for (heading, listing_dict, _) in self.sections
            for k in listing_dict.keys()]
        if len(all_keys) == 0:
            return
        column_width = max(map(len, all_keys)) + 1
        for (heading, listing_dict, empty_msg) in self.sections:
            empty = len(listing_dict) == 0
            print("\n" + heading + (empty and "\n " + empty_msg or ""))
            if not empty:
                for (k, v) in listing_dict.items():
                    print(("%" + str(column_width) + "s: %s") % (k, v))


##############################################
# subprocess stuff
##############################################

# TODO consolidate with _shell
def _shell_get_output(cmd_str, working_dir):
    process = subprocess.Popen(
        cmd_str,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=file("/dev/null", "w"),
        close_fds=True,
        cwd=working_dir)

    return process.communicate()[0]


STREAM = "stream"
BUFFER = "buffer"
NULL = "null"


def _shell(cmd_str, working_dir, output_mode=STREAM):
    if output_mode == STREAM:
        out_file = None
    elif output_mode == BUFFER:
        out_file = tempfile.NamedTemporaryFile()
    elif output_mode == NULL:
        out_file = open(os.devnull, 'w')
    else:
        raise Error("Unknown output_mode '%s'" % output_mode)

    # Write the command into a file and invoke bash on it
    cmd_file = tempfile.NamedTemporaryFile()
    cmd_file.write("""
echo 'cd %s'
cat <<ADS_EOF
%s
ADS_EOF
%s
""" % (working_dir, cmd_str, cmd_str))
    cmd_file.flush()
    try:
        status = subprocess.Popen(
            ["/bin/bash", cmd_file.name],
            close_fds=True,
            cwd=working_dir,
            # Same file for stdout and stderr to preserve order (roughly)
            stdout=out_file,
            stderr=out_file).wait()
    except KeyboardInterrupt:
        # Suppress python from printing a stack trace
        status = 47
        pass
    cmd_file.close()

    if output_mode == BUFFER:
        out_file.seek(0)
        output = out_file.read()
        out_file.close()
        return status, output
    else:
        return status, None


##############################################
# YML stuff
##############################################

class ParseProjectException(Exception):
    def __init__(self, msg):
        super(ParseProjectException, self).__init__(msg)


def _expect(expected_type, actual, origin_file):
    if not isinstance(actual, expected_type):
        raise ParseProjectException(
            "%s: Expected %s, got %s: %s" %
            (origin_file, str(expected_type), type(actual), str(actual)))


def _load_spec_file(path):
    result = yaml.safe_load(file(path, "r").read()) or {}
    _expect(dict, result, path)
    return result


##############################################
# Service
##############################################

def _abs_to_cwd_rel(abspath):
    return os.path.relpath(abspath, os.path.abspath(os.curdir))


class Service:
    @classmethod
    def load(cls, svc_yml, name):
        spec = _load_spec_file(svc_yml)
        return Service(name,
                       os.path.dirname(svc_yml),
                       spec.get("description"),
                       spec.get("start_cmd"),
                       spec.get("stop_cmd"),
                       spec.get("status_cmd"),
                       spec.get("log_paths"),
                       spec.get("err_log_paths"))

    @classmethod
    def as_printable_dict(cls, services):
        return dict([
            (s.name, s.get_description_or_default()) for s in services])

    def __init__(self, name, home, description=None,
                 start_cmd=None, stop_cmd=None, status_cmd=None,
                 log_paths=None, err_log_paths=None):

        self.name = name
        self.home = home
        self.description = description

        self.start_cmd = start_cmd
        self.stop_cmd = stop_cmd
        self.status_cmd = status_cmd

        self.log_paths = log_paths or []
        self.err_log_paths = err_log_paths or []

    def resolve_logs_relative_to_cwd(self, log_type):
        if log_type == "general":
            log_paths = self.log_paths
        elif log_type == "error":
            log_paths = self.err_log_paths
        else:
            assert False, "Unknown log_type %s" % log_type

        result = []
        for logfile in log_paths:
            abs_log_glob = os.path.join(self.home, logfile)
            result = result + [
                _abs_to_cwd_rel(abs_log_file)
                for abs_log_file
                in glob.iglob(abs_log_glob)]
        return result

    def resolve_home_relative_to_cwd(self):
        return _abs_to_cwd_rel(self.home)

    def get_description_or_default(self):
        return self.description or "(No description)"

    def __repr__(self):
        return self.name


##############################################
# ServiceSet
##############################################

class BadSelectorException(Exception):
    def __init__(self, msg):
        super(BadSelectorException, self).__init__(msg)


def _resolve(selector, project, service_sets_by_name, selector_stack):
    assert selector

    if selector in selector_stack:
        stack_as_list = list(selector_stack) + [selector]
        raise BadSelectorException(
            "Definition of selector '%s' is circular: %s" %
            (stack_as_list[0], " -> ".join(stack_as_list)))

    if selector == "all":
        return frozenset(project.services_by_name.keys())

    if selector in project.services_by_name:
        return frozenset([project.services_by_name[selector].name])

    if selector in service_sets_by_name:
        selector_stack[selector] = True
        sub_results = map(lambda s: _resolve(s,
                                             project,
                                             service_sets_by_name,
                                             selector_stack),
                          service_sets_by_name[selector].selectors)
        selector_stack.popitem(True)
        return frozenset(reduce(frozenset.__or__, sub_results))

    stack_as_list = list(selector_stack) + [selector]
    raise BadSelectorException(
        "No service or selector named '%s'. Reference chain: %s" %
        (selector, " -> ".join(stack_as_list)))


class ServiceSet:
    @classmethod
    def load(cls, name, spec, origin_file):
        _expect(list, spec, origin_file)
        selectors = []
        for selector in spec:
            _expect(str, selector, origin_file)
            selectors.append(selector)
        return ServiceSet(name, selectors)

    @classmethod
    def load_multiple(cls, spec, origin_file):
        spec = spec or {}
        _expect(dict, spec, origin_file)
        return [ServiceSet.load(name, value, origin_file)
                for (name, value)
                in spec.items()]

    @classmethod
    def load_default(cls, spec, origin_file):
        if not spec:
            return None
        _expect(str, spec, origin_file)
        return spec

    @classmethod
    def resolve(cls, selector, project, service_sets):
        return _resolve(selector,
                        project,
                        dict((s.name, s) for s in service_sets),
                        OrderedDict())

    @classmethod
    def as_printable_dict(cls, service_sets):
        return dict([(s.name, ', '.join(s.selectors)) for s in service_sets])

    def __init__(self, name, selector_set):
        self.name = name
        self.selectors = selector_set


##############################################
# Project
##############################################

def _find_project_yml(search_start):
    maybe_root = os.path.join(search_start, "adsroot.yml")
    if os.path.isfile(maybe_root):
        return maybe_root
    parent = os.path.dirname(search_start)
    if parent == search_start:
        return None
    else:
        return _find_project_yml(parent)


def _find_service_ymls(project_root):
    find_output = _shell_get_output(
        "/usr/bin/find . -mindepth 2 -name ads.yml -or -name adsroot.yml",
        project_root).splitlines()

    nested_project_dirs = [
        os.path.dirname(path)
        for path in find_output
        if os.path.basename(path) == "adsroot.yml"
    ]

    def in_nested_project_dir(path_str):
        for dir_path in nested_project_dirs:
            if path_str.startswith(dir_path):
                return True
        return False

    # BEWARE: O(n*m) algorithm!
    return [
        os.path.join(project_root, p)
        for p in find_output
        if os.path.basename(p) == "ads.yml" and not in_nested_project_dir(p)
    ]


def _adsfiles_to_service_names(adsfiles):
    svc_name_to_file = {}
    file_to_svc_name = {}
    for f in adsfiles:
        basename = os.path.basename(os.path.dirname(f))
        if basename in svc_name_to_file:
            raise Exception("not yet implemented")  # TODO
        svc_name_to_file[basename] = f
        file_to_svc_name[f] = basename
    return file_to_svc_name


class Project:
    @classmethod
    def load_from_dir(cls, root_dir):
        project_yml = _find_project_yml(os.path.abspath(root_dir))
        if not project_yml:
            return None

        service_ymls = _find_service_ymls(os.path.dirname(project_yml))
        return Project.load_from_files(project_yml, service_ymls)

    @classmethod
    def load_from_files(cls, project_yml, svc_ymls):
        spec = _load_spec_file(project_yml)
        home = os.path.dirname(project_yml)
        name = spec.get("name") or os.path.basename(home)
        services = [
            Service.load(svc_file, svc_name)
            for (svc_file, svc_name)
            in _adsfiles_to_service_names(svc_ymls).items()
        ]
        service_sets = ServiceSet.load_multiple(
            spec.get("groups"), project_yml)
        default_selector = ServiceSet.load_default(
            spec.get("default"), project_yml) or "all"
        return Project(name, home, services, service_sets, default_selector)

    def __init__(self,
                 name, home,
                 services=None, service_sets=None,
                 default_selector="all"):
        self.name = name
        self.home = home
        self.services_by_name = dict((s.name, s) for s in (services or []))
        self.service_sets = service_sets or []
        self.default_selector = default_selector


##############################################
# Profile
##############################################

class Profile:
    @classmethod
    def load_from_dir(cls, profile_dir):
        rc_path = os.path.join(profile_dir, ".ads_profile.yml")
        if not os.path.isfile(rc_path):
            return Profile()

        rc_spec = _load_spec_file(rc_path)
        return Profile(
            ServiceSet.load_multiple(rc_spec.get("groups"), rc_path),
            ServiceSet.load_default(rc_spec.get("default"), rc_path))

    def __init__(self, service_sets=None, default_selector=None):
        self.service_sets = service_sets or []
        self.default_selector = default_selector


##############################################
# Ads
##############################################

class Ads:
    @staticmethod
    def load_from_fs(root_dir, profile_dir):
        project = Project.load_from_dir(root_dir)
        if not project:
            return None

        profile = Profile.load_from_dir(profile_dir) or Profile()
        return Ads(project, profile)

    @staticmethod
    def load_from_env():
        profile_home = os.getenv("ADS_PROFILE_HOME")
        if not profile_home or len(profile_home) == 0:
            profile_home = os.path.expanduser("~")
        return Ads.load_from_fs(os.curdir, profile_home)

    def __init__(self, project, profile=Profile()):
        self.project = project
        self.profile = profile

    def resolve(self, selector):

        if selector == "default":
            selector = self.get_default_selector()

        return ServiceSet.resolve(
            selector,
            self.project,
            self.project.service_sets + self.profile.service_sets)

    def get_default_selector(self):
        return (self.profile.default_selector or
                self.project.default_selector)

    def list(self):
        default_selector = self.get_default_selector()
        try:
            default_description = ', '.join(self.resolve(default_selector))
        except BadSelectorException:
            default_description = "(Unresolved)"
        if default_description == default_selector:
            default_service = self.project.services_by_name[default_selector]
            default_description = default_service.get_description_or_default()

        (Treelisting()
         .with_section(
            "All services in current project (%s):" % self.project.name,
            Service.as_printable_dict(self.project.services_by_name.values()),
            "None (create ads.yml files in this dir tree)")
         .with_section(
            "Groups defined in current project:",
            ServiceSet.as_printable_dict(self.project.service_sets),
            "None (add 'groups' to adsroot.yml)")
         .with_section(
            "Groups defined in your ads profile:",
            ServiceSet.as_printable_dict(self.profile.service_sets),
            "None (add 'groups' to ~/.ads_profile.yml)")
         .with_section(
            "Default service for commands if none are specified:",
            {default_selector: default_description})
        ).pretty_print()


##############################################
# Customized ArgumentParser
##############################################

class MyArgParser(argparse.ArgumentParser):
    def error(self, message):
        if "too few arguments" in message:
            # Default behavior of "ads" is too punishing
            # This behavior matches git
            self.print_help()
            sys.exit(2)
        else:
            super(MyArgParser, self).error(message)


##############################################
# AdsCommand
##############################################

class AdsCommandException(Exception):
    def __init__(self, exit_code, msg=None):
        self.exit_code = exit_code
        self.msg = msg


class UsageError(AdsCommandException):
    def __init__(self, msg):
        super(UsageError, self).__init__(2, msg)


class NotFound(AdsCommandException):
    def __init__(self, msg):
        super(NotFound, self).__init__(11, msg)


class InternalError(AdsCommandException):
    def __init__(self, msg):
        super(InternalError, self).__init__(50, msg)


class StartFailed(AdsCommandException):
    def __init__(self, msg):
        super(StartFailed, self).__init__(21, msg)


class StopFailed(AdsCommandException):
    def __init__(self, msg):
        super(StopFailed, self).__init__(22, msg)


class SomeDown(AdsCommandException):
    def __init__(self):
        super(SomeDown, self).__init__(23)


def _load_or_die():
    ads = Ads.load_from_env()
    if not ads:
        raise UsageError(
            "ads must be run from within an ads project. "
            "See README for more.")
    return ads


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


def _is_running(service, verbose):
    return _shell(service.status_cmd,
                  service.home,
                  verbose and STREAM or NULL)[0] == 0


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
    attempts = 0
    info("Stopping %s" % service.name)
    while True:
        (status, out) = _shell(service.stop_cmd, service.home,
                               verbose and STREAM or BUFFER)
        attempts = attempts + 1

        if status == 0:
            if verbose:
                debug("Stop command succeeded")
        else:
            error("Stop command failed")
            if not verbose:
                sys.stderr.write(out)
                error(separator())
            else:
                # Output was already streamed
                pass
            return False

        if not _is_running(service, verbose):
            if verbose:
                debug("Status says %s is down" % service.name)
            return True

        elif attempts > 10:
            error(("Stop command succeeded, but status says %s " +
                   "is still running. This is a bug in your ads.yml. " +
                   "If you can reproduce this, try with -v to debug.")
                  % service.name)
            return False

        else:
            if verbose:
                debug("%s is still running after stop command; retrying" %
                      service.name)
            time.sleep(0.5)


def _collect_rel_homes(services):
    return [s.resolve_home_relative_to_cwd() for s in services]


def _add_verbose_arg(parser):
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show output of commands that ads delegates to")


def _add_services_arg(parser):
    parser.add_argument(
        "service",
        nargs="*",
        help="The services or groups to act on")


def _resolve_selectors(ads, selectors, fail_if_empty):
    if len(selectors) == 0:
        selectors = ["default"]

    try:
        service_names = reduce(frozenset.__or__,
                               [ads.resolve(s) for s in selectors])
    except BadSelectorException as e:
        raise NotFound(str(e))

    services = map(
        lambda name: ads.project.services_by_name[name],
        sorted(service_names))

    if fail_if_empty and len(services) == 0:
        raise NotFound("No services found that match '%s'" %
                       ' '.join(selectors))

    return services


def _collect_logs_nonempty(services, log_type):
    all_logs = []
    for s in services:
        all_logs += s.resolve_logs_relative_to_cwd(log_type)

    if len(all_logs) == 0:
        raise NotFound("No %s log files found for services %s" %
                       (log_type, str(services)))

    return all_logs


def list_func(args):
    parser = MyArgParser(prog=cmd_list.name, description=cmd_list.description)
    parser.parse_args(args)
    ads = _load_or_die()
    ads.list()


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


def down(args):
    parser = MyArgParser(prog=cmd_down.name, description=cmd_down.description)
    _add_verbose_arg(parser)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    if not all(map(lambda sp: _down(sp, parsed_args.verbose), services)):
        raise StopFailed("One or more services failed to stop")


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


def home(args):
    parser = MyArgParser(prog=cmd_home.name, description=cmd_home.description)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    ads = _load_or_die()
    services = _resolve_selectors(ads, parsed_args.service, True)
    print("\n".join(_collect_rel_homes(services)))


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


class Cmd:
    def __init__(self, name, func, description, is_common=False, aliases=None):
        self.name = name
        self.func = func
        self.description = description
        self.is_common = is_common
        self.aliases = aliases or []


cmd_help = Cmd(
    "help", None,
    "Display help about ads")
cmd_list = Cmd(
    "list", list_func,
    "Print the list of available services", True)
cmd_up = Cmd(
    "up", up,
    "Ensure the specified services are running", True,
    ["start", "run"])
cmd_down = Cmd(
    "down", down,
    "Ensure the specified services are not running", True,
    ["stop", "kill"])
cmd_status = Cmd(
    "status", status,
    "Print status of the specified services", True)
cmd_logs = Cmd(
    "logs", logs,
    "Tail the logs of the specified services", True)
cmd_bounce = Cmd(
    "bounce", bounce,
    "Stop and restart the specified services", False,
    ["restart"])
cmd_home = Cmd(
    "home", home,
    "Print paths to the specified services' home directories")
cmd_edit = Cmd(
    "edit", edit,
    "Edit a service's ads.yml")
all_cmds = [cmd_help, cmd_list, cmd_up, cmd_down, cmd_status, cmd_logs,
            cmd_bounce, cmd_home, cmd_edit]

cmds_by_alias = dict([
    (name, cmd)
    for cmd in all_cmds
    for name in ([cmd.name] + cmd.aliases)])


##############################################
# main
##############################################

def fail(exit_status, msg=None):
    if msg:
        error(msg)
    exit(exit_status)


def format_help_for_cmds(cmds):
    return "\n".join(["   %-10s %s" % (c.name, c.description) for c in cmds])


def create_main_arg_parser():
    epilog = """
The most commonly used ads commands are:
%s

Some less common commands:
%s

See 'ads help <command>' to read about a specific subcommand.
""" % (format_help_for_cmds(filter(lambda cmd: cmd.is_common, all_cmds)),
       format_help_for_cmds(filter(lambda cmd: not cmd.is_common, all_cmds)))
    usage = "ads [-h] <command> [args] [service [service ...]]"
    parser = MyArgParser(
        prog="ads",
        description="Start, stop, and manage microservices in a codebase",
        epilog=epilog,
        usage=usage,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "command",
        metavar="<command>",
        choices=cmds_by_alias.keys(),
        help="Do something to a service")
    return parser


main_parser = create_main_arg_parser()


def help(args):
    parser = MyArgParser(prog=cmd_help.name, description=cmd_help.description)
    parser.add_argument(
        "command",
        metavar="<command>",
        nargs="?",
        choices=cmds_by_alias.keys(),
        help="command to learn about")
    parsed_args = parser.parse_args(args)
    if parsed_args.command:
        cmds_by_alias[parsed_args.command].func(["-h"])
    else:
        main_parser.print_help()


cmds_by_alias["help"].func = help


def main():
    cmd_args = sys.argv[1:2]
    subcmd_args = sys.argv[2:]

    args = main_parser.parse_args(cmd_args)
    if args.command == "help" and len(subcmd_args) == 0:
        main_parser.print_help()
        return

    try:
        cmds_by_alias[args.command].func(subcmd_args)
    except AdsCommandException as e:
        fail(e.exit_code, e.msg)
