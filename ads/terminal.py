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
