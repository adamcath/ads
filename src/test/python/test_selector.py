import unittest
from ads import Ads, Project, Service, ServiceSet, Profile, BadSelectorException

some_services = [Service("a", "/a"),
                 Service("b", "/b"),
                 Service("c", "/c"),
                 Service("d", "/d")]
a_and_b = ServiceSet("a-and-b", frozenset(["a", "b"]))
b_and_c = ServiceSet("b-and-c", frozenset(["b", "c"]))


class TestSelectors(unittest.TestCase):

    def test_selector_is_service_name(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services))
            .resolve("b"),
            frozenset(["b"]))

    def test_all_selector(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services))
            .resolve("all"),
            frozenset(["a", "b", "c", "d"]))

    def test_set_defined_in_project(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services, [a_and_b]))
            .resolve("a-and-b"),
            frozenset(["a", "b"]))

    def test_set_defined_in_profile(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services),
                Profile([b_and_c]))
            .resolve("b-and-c"),
            frozenset(["b", "c"]))

    def test_when_same_set_in_project_and_profile_the_latter_wins(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services, [a_and_b]),
                Profile([ServiceSet("a-and-b", frozenset(["a", "c"]))]))
            .resolve("a-and-b"),
            frozenset(["a", "c"]))
        pass

    def test_recursive_selectors_across_project_and_profile(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services,
                        [ServiceSet("team-foo", frozenset(["ab", "d"]))]),
                Profile([ServiceSet("ab", frozenset(["a", "b"]))]))
            .resolve("team-foo"),
            frozenset(["a", "b", "d"]))
        pass

    def test_selector_resolves_to_nonexistent_service(self):
        ads = Ads(Project("test", "/test", [],
                          [ServiceSet("ab", frozenset(["a", "b"]))]))
        self.assertRaisesRegexp(
            BadSelectorException, "No service .* ab -> a", ads.resolve, "ab")
        pass

    def test_unknown_selector(self):
        ads = Ads(Project("test", "/test"))
        self.assertRaisesRegexp(
            BadSelectorException, "No service", ads.resolve, "ab")
        pass

    def test_circular_selectors(self):
        ads = Ads(Project("test", "/test", some_services,
                          [ServiceSet("foo", frozenset(["bar"]))]),
                  Profile([ServiceSet("bar", frozenset(["foo"]))]))
        self.assertRaisesRegexp(
            BadSelectorException, "foo -> bar -> foo", ads.resolve, "foo")
        self.assertRaisesRegexp(
            BadSelectorException, "bar -> foo -> bar", ads.resolve, "bar")
        pass

    def test_default_selector_when_defined_in_project(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services, [], "b"))
            .resolve("default"),
            frozenset(["b"]))
        pass

    def test_default_selector_when_defined_in_profile(self):
        self.assertEqual(
            Ads(Project("test", "/test", some_services, []),
                Profile([], "c"))
            .resolve("default"),
            frozenset(["c"]))
        pass

if __name__ == '__main__':
    unittest.main()