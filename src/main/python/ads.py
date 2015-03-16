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
            print("\n" + heading + (empty and "\n " + empty_msg or ""))
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
    return status


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

    status = _shell("tail -F " + " \\\n\t".join(project_rel_files), project.home)
    return (status == 0 or
            status == 47)  # tail was ended by ctrl+c (Mac OS)


def _cat(files):
    return _shell("cat " + " ".join(files), os.curdir) == 0


def _status(service):
    if not service.status_cmd:
        status = False
        msg = "status command not defined"
    else:
        status = _shell(service.status_cmd, service.home) == 0
        msg = status and "ok" or "not running"
    info(service.name + ": " + msg)
    return status


def _is_running(service):
    return _shell(service.status_cmd, service.home) == 0


def _up(service):
    if not service.status_cmd:
        error("Status command not defined for " + service.name +
              "; can't tell if it's already running")
        return False

    info("Checking if %s is already running" % service.name)
    if _is_running(service):
        info(service.name + " is already running")
        return True
    if not service.start_cmd:
        error("Start command not defined for " + service.name)
        return False
    else:
        info("Starting " + service.name)
        success = _shell(service.start_cmd, service.home) == 0
        if success:
            info("Started " + service.name)
        else:
            error("Failed to start " + service.name)
        return success


def _down(service):
    if not service.status_cmd:
        error("Status command not defined for " + service.name +
              "; can't tell if it's already stopped")
        return False

    info("Checking if %s is running" % service.name)
    if not _is_running(service):
        info(service.name + " is already stopped")
        return True
    if not service.stop_cmd:
        error("Stop command not defined for " + service.name)
        return False
    else:
        info("Stopping %s" % service.name)
        success = _shell(service.stop_cmd, service.home) == 0
        if success:
            info("Stopped " + service.name)
        else:
            error("Failed to stop " + service.name)
        return success


def _collect_rel_homes(services):
    return [s.resolve_home_relative_to_cwd() for s in services]


def _add_services_arg(parser):
    parser.add_argument(
        "service",
        nargs="*",
        help="The services or groups to act on")


def _default_cli(cmd, ads, args, fail_if_no_services=True):
    parser = MyArgParser(prog=cmd)
    _add_services_arg(parser)
    parsed_args = parser.parse_args(args)
    return _resolve_selectors(ads, parsed_args.service, fail_if_no_services)


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


class AdsCommand:

    verbs = [
        "help",
        "list",
        "up", "down", "bounce", "status",
        "logs",
        "home"]
    verb_aliases = {
        "start": "up", "run": "up",
        "stop": "down", "kill": "down",
        "restart": "bounce"}

    def __init__(self):
        pass

    @classmethod
    def execute(cls, verb, ads, args):
        assert isinstance(verb, str)
        assert isinstance(args, list)
        assert isinstance(ads, Ads)

        if verb in AdsCommand.verb_aliases:
            verb = AdsCommand.verb_aliases[verb]

        func_name = verb.replace("-", "_")
        try:
            closure = getattr(AdsCommand(), func_name)
        except:
            raise InternalError("Bad command '%s'" % verb)
        closure(ads, args)

    def help(self, ads, args):
        AdsCommand.execute(args[0], ads, ["-h"])

    def list(self, ads, _):
        ads.list()

    def up(self, ads, args):
        services = _default_cli("up", ads, args)
        info("Starting " + str(services))
        if not all(map(lambda sp: _up(sp), services)):
            raise StartFailed("One or more services failed to start")

    def down(self, ads, args):
        services = _default_cli("down", ads, args)
        if not all(map(lambda sp: _down(sp), services)):
            raise StopFailed("One or more services failed to stop")

    def bounce(self, ads, args):
        services = _default_cli("bounce", ads, args)
        all_stopped = all(map(lambda sp: _down(sp), services))
        all_started = all(map(lambda sp: _up(sp), services))
        if not all_stopped:
            raise StopFailed("One or more services failed to stop")
        if not all_started:
            raise StartFailed("One or more services failed to restart")

    def status(self, ads, args):
        services = _default_cli("status", ads, args, False)
        if not all(map(lambda sp: _status(sp), services)):
            raise SomeDown()

    def logs(self, ads, args):

        parser = MyArgParser(prog="logs")
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

    def home(self, ads, args):
        services = _default_cli("home", ads, args)
        print("\n".join(_collect_rel_homes(services)))


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
  status      Print status of the specified services
  logs        Tail the logs of the specified services

Some less common commands:
  bounce      Stop and restart the specified services
  home        Print paths to the specified services' home directories

See 'ads help <command>' to read about a specific subcommand.
"""

    usage = "ads [-h] <command> [args] [service [service ...]]"

    all_commands = AdsCommand.verbs + AdsCommand.verb_aliases.keys()

    parser = MyArgParser(
        prog="ads",
        description="Start, stop, and manage microservices in a codebase",
        epilog=epilog,
        usage=usage,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "command",
        metavar="<command>",
        choices=all_commands,
        help="Do something to a service")

    args = parser.parse_args(sys.argv[1:2])

    profile_home = os.getenv("ADS_PROFILE_HOME")
    if not profile_home or len(profile_home) == 0:
        profile_home = os.path.expanduser("~")

    ads = Ads.load(os.curdir, profile_home)
    if not ads:
        fail(1, "ads must be run from within an ads project. "
                "See README for more.")

    try:
        AdsCommand.execute(args.command, ads, sys.argv[2:])
    except AdsCommandException as e:
        fail(e.exit_code, e.msg)

if __name__ == "__main__":
    main()
