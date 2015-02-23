#!/usr/bin/python
#
# Main entry point for ads. See README for overall description; run with -h for
# usage.
#
# @author adamcath


import sys


def debug(msg):
    print(msg)
    sys.stdout.flush()


def info(msg):
    print("--- " + msg)
    sys.stdout.flush()


def error(msg):
    sys.stderr.write("!!! " + msg + "\n")
    sys.stderr.flush()


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
            print("\n" + heading + (empty and " - " + empty_msg or ""))
            if not empty:
                for (k, v) in listing_dict.items():
                    print(("%" + str(column_width) + "s: %s") % (k, v))


##############################################
# subprocess stuff
##############################################

def _shell_get_output(cmd_str, working_dir):
    process = subprocess.Popen(
        cmd_str,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=file("/dev/null", "w"),
        close_fds=True,
        cwd=working_dir)

    return process.communicate()[0]


def _shell(cmd_str, working_dir, quiet=False):
    if not quiet:
        debug("cd " + working_dir)
    # TODO Can we avoid this nonsense using shell=true?
    cmd_file = tempfile.NamedTemporaryFile()
    cmd_file.write(cmd_str)
    cmd_file.flush()
    if not quiet:
        debug(cmd_str)
    try:
        status = subprocess.Popen(
            ["/bin/bash", cmd_file.name],
            close_fds=True,
            cwd=working_dir,
            stdout=quiet and file("/dev/null", "w") or None,
            stderr=quiet and file("/dev/null", "w") or None).wait()
    except KeyboardInterrupt:
        # Suppress python from printing a stack trace
        status = 47
        pass
    cmd_file.close()
    return status == 0


def _shell_quiet(cmd_str, working_dir):
    return _shell(cmd_str, working_dir, True)


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

class Service:

    @classmethod
    def load(cls, svc_yml, name):
        spec = _load_spec_file(svc_yml)
        return Service(name,
                       os.path.dirname(svc_yml),
                       spec.get("description"),
                       spec.get("start"),
                       spec.get("stop"),
                       spec.get("status"),
                       spec.get("logs"))

    @classmethod
    def as_printable_dict(cls, services):
        return dict([
            (s.name, s.description or "(No description)") for s in services])

    def __init__(self, name, home, description=None,
                 start=None, stop=None, status=None, logs=None):

        self.name = name
        self.home = home
        self.description = description

        self.start = start
        self.stop = stop
        self.status = status

        self.logs = logs or []

    def resolve_logs_relative_to_cwd(self):
        result = []
        for logfile in self.logs:
            abs_log_glob = os.path.join(self.home, logfile)
            result = result + [
                os.path.relpath(
                    abs_log_file,
                    os.path.abspath(os.curdir))
                for abs_log_file
                in glob.iglob(abs_log_glob)]
        return result


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
            raise Exception("not yet implemented")
        svc_name_to_file[basename] = f
        file_to_svc_name[f] = basename
    return file_to_svc_name


class Project:
    root_project = None
    services_by_name = {}

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
        name = spec.get("name") or "project(%s)" % os.path.basename(home)
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
        rc_path = os.path.join(profile_dir, ".adsrc")
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

    @classmethod
    def load(cls, root_dir, profile_dir):
        project = Project.load_from_dir(root_dir)
        if not project:
            return None

        profile = Profile.load_from_dir(profile_dir) or Profile()
        return Ads(project, profile)

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
        default_selector_resolution = "(Unresolved)"
        try:
            default_selector_resolution = ', '.join(self.resolve(default_selector))
        except BadSelectorException:
            pass

        (Treelisting()
            .with_section(
                "All known services",
                Service.as_printable_dict(self.project.services_by_name.values()),
                "None (create ads.yml files in this dir tree)")
            .with_section(
                "Groups from user preferences",
                ServiceSet.as_printable_dict(self.profile.service_sets),
                "None (add 'groups' to ~/.asrc)")
            .with_section(
                "Groups from project",
                ServiceSet.as_printable_dict(self.project.service_sets),
                "None (add 'groups' to adsroot.yml)")
            .with_section(
                "Default service/group",
                {default_selector: default_selector_resolution})
         ).pretty_print()


##############################################
# AdsCommand
##############################################

class AdsCommandException(Exception):
    def __init__(self, exit_code, msg=None):
        self.exit_code = exit_code
        self.msg = msg


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


def _tail(files, project):
    project_rel_files = [
        os.path.relpath(os.path.abspath(f), project.home)
        for f in files]
    return _shell(
        "tail -F " + " \\\n\t".join(project_rel_files),
        project.home)


def _cat(files):
    return _shell("cat " + " ".join(files), os.curdir)


def _status(service):
    if not service.status:
        status = False
        msg = "status command not defined"
    else:
        status = _shell_quiet(service.status, service.home)
        msg = status and "ok" or "not running"
    info(service.name + ": " + msg)
    return status


def _is_running(service):
    return _shell_quiet(service.status, service.home)


def _up(service):
    if not service.status:
        error("Status command not defined for " + service.name +
              "; can't tell if it's already running")
        return False
    if _is_running(service):
        info(service.name + " is already running.")
        return True
    if not service.start:
        error("Start command not defined for " + service.name)
        return False
    else:
        success = _shell(service.start, service.home)
        if success:
            info("Started " + service.name)
        else:
            error("Failed to start " + service.name)
        return success


def _down(service):
    if not service.status:
        error("Status command not defined for " + service.name +
              "; can't tell if it's already stopped")
        return False
    if not _is_running(service):
        info(service.name + " is already stopped.")
        return True
    if not service.stop:
        error("Stop command not defined for " + service.name)
        return False
    else:
        success = _shell(service.stop, service.home)
        if success:
            info("Stopped " + service.name)
        else:
            error("Failed to stop " + service.name)
        return success


def _collect_logs(services):
    result = []
    for sp in services:
        result += sp.resolve_logs_relative_to_cwd()
    return result


class AdsCommand:

    verbs = ["up", "down", "bounce", "status", "logs", "cat-logs", "list-logs"]
    verb_aliases = {
        "start": "up", "run": "up",
        "stop": "down", "kill": "down",
        "restart": "bounce"}

    def __init__(self, verb=None, selectors=None):
        assert isinstance(verb, str)
        assert isinstance(selectors, list)

        if verb in AdsCommand.verb_aliases:
            verb = AdsCommand.verb_aliases[verb]
        self.verb = verb
        self.selectors = selectors

    def execute(self, ads):

        try:
            service_names = reduce(frozenset.__or__,
                                   [ads.resolve(s) for s in self.selectors])
        except BadSelectorException as e:
            raise NotFound(str(e))

        services = map(
            lambda name: ads.project.services_by_name[name],
            sorted(service_names))

        def assert_services_nonempty():
            if len(services) == 0:
                raise NotFound("No services found that match '%s'" %
                               ' '.join(self.selectors))

        def collect_logs_nonempty(use_msg):
            all_logs = _collect_logs(services)
            if len(all_logs) == 0:
                raise NotFound(
                    use_msg and
                    "No log files found for services " + str(services) or
                    None)
            return all_logs

        if self.verb == "up":
            assert_services_nonempty()
            if not all(map(lambda sp: _up(sp), services)):
                raise StartFailed("One or more services failed to start")

        elif self.verb == "down":
            assert_services_nonempty()
            if not all(map(lambda sp: _down(sp), services)):
                raise StopFailed("One or more services failed to stop")

        elif self.verb == "bounce":
            assert_services_nonempty()
            all_stopped = all(map(lambda sp: _down(sp), services))
            all_started = all(map(lambda sp: _up(sp), services))
            if not all_stopped:
                raise StopFailed("One or more services failed to stop")
            if not all_started:
                raise StartFailed("One or more services failed to restart")

        elif self.verb == "status":
            if not all(map(lambda sp: _status(sp), services)):
                raise SomeDown()

        elif self.verb == "logs":
            if not _tail(collect_logs_nonempty(True), ads.project):
                raise InternalError("tail command failed")

        elif self.verb == "list-logs":
            print("\n".join(collect_logs_nonempty(False)))

        elif self.verb == "cat-logs":
            if not _cat(collect_logs_nonempty(False)):
                raise InternalError("cat command failed")

        else:
            raise InternalError("Bad command '%s'" % self.verb)


##############################################
# main
##############################################

def fail(exit_status, msg=None):
    if msg:
        error(msg)
    exit(exit_status)


def main():

    epilog = """
The most commonly used ads commands are:
  list        Print the list of available services
  up          Ensure the specified services are running
  down        Ensure the specified services are not running
  bounce      Stop and restart the specified services
  status      Print status of the specified services
  logs        Tail the logs of the specified services

Some less common commands:
  cat-logs    Print logs to stdout
  list-logs   Print paths to log files to stdout (for pipelining) 
"""

    all_commands = (AdsCommand.verbs +
                    AdsCommand.verb_aliases.keys() +
                    ["list", "help"])

    parser = argparse.ArgumentParser(
        prog="ads",
        description="Start, stop, and manage microservices in a codebase",
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "command",
        metavar="<command>",
        choices=all_commands,
        help="Do something to a service")
    parser.add_argument(
        "service",
        nargs="*",
        help="The services or groups to act on")

    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
        return

    profile_home = os.getenv("ADS_PROFILE_HOME")
    if not profile_home or len(profile_home) == 0:
        profile_home = os.path.expanduser("~")

    ads = Ads.load(os.curdir, profile_home)
    if not ads:
        fail(1, "ads must be run from within an ads project. "
                "See README for more.")

    if len(args.service) == 0:
        args.service = ["default"]

    if args.command == "list":
        ads.list()
        return

    try:
        AdsCommand(args.command, args.service).execute(ads)
    except AdsCommandException as e:
        fail(e.exit_code, e.msg)

if __name__ == "__main__":
    main()
