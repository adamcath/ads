cmd_list = Cmd(
    "list", list_func,
    "Print the list of available services", True)

def list_func(args):
    parser = MyArgParser(prog=cmd_list.name, description=cmd_list.description)
    parser.parse_args(args)
    ads = _load_or_die()
    ads.list()


