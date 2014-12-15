import unittest
import ads

foo_service = ads.Service("foo", "/foo")


class TestUserErrors(unittest.TestCase):

    def test_status_when_not_defined(self):
        ads._status(foo_service)
        # TODO assert error with "status command not defined"

    def test_up_when_status_not_defined(self):
        ads._up(foo_service)
        # TODO assert error with "Status command not defined"

    def test_down_when_status_not_defined(self):
        ads._down(foo_service)
        # TODO assert error with "Status command not defined"