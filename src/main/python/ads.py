#!/usr/bin/python
#
# Main entry point for ads. See README for overall description; run with -h for
# usage.
#
# @author adamcath

import argparse


def format_help_for_cmds(cmds):
    return "\n".join(["   %-10s %s" % (c.name, c.description) for c in cmds])


def create_main_arg_parser(all_cmds, cmds_by_alias):
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


def create_help_func(cmd_help, cmds_by_alias, main_parser):
    def help(args):
        parser = MyArgParser(prog=cmd_help.name,
                             description=cmd_help.description)
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

    return help


def main():
    # Find all commands (anything on PYTHONPATH starting with ads_)
    # Load the definition (currently the Cmd object)
    # To run it, just fork to it, passing the subcmd_args as the args

    all_cmds = [cmd_help, cmd_list, cmd_up, cmd_down, cmd_status, cmd_logs,
                cmd_bounce, cmd_home, cmd_edit]

    cmds_by_alias = dict([
        (name, cmd)
        for cmd in all_cmds
        for name in ([cmd.name] + cmd.aliases)])

    main_parser = create_main_arg_parser(all_cmds, cmds_by_alias)

    cmds_by_alias["help"].func = create_help_func(
        cmd_help, cmds_by_alias, main_parser)

    cmd_args = sys.argv[1:2]
    subcmd_args = sys.argv[2:]

    args = main_parser.parse_args(cmd_args)
    if args.command == "help" and len(subcmd_args) == 0:
        main_parser.print_help()
        return 0

    try:
        cmds_by_alias[args.command].func(subcmd_args)
    except AdsCommandException as e:
        if e.msg:
            error(e.msg)
        return e.exit_code


if __name__ == "__main__":
    exit(main())