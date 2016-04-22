#!/usr/bin/env bash

test_empty_dir_gives_error() {
    go_test_project empty-dir
    assert_fails "ads list" "within an ads project"
    assert_fails "ads up" "within an ads project"
    assert_fails "ads down" "within an ads project"
    assert_fails "ads home" "within an ads project"
}

test_root_with_no_services_gives_error() {
    go_test_project root-but-no-services
    assert_fails "ads up" "No services"
    assert_fails "ads down" "No services"
    assert_contains "$(ads list)" \
        "None (create ads.yml" \
        "Groups defined in current project" \
        "None (add 'groups' to adsroot.yml)" \
        "Groups defined in your ads profile" \
        "None (add 'groups' to ~/.ads_profile.yml)" \
        "Default service" \
        "all"
    assert_fails_silently "ads logs --list"
    assert_fails_silently "ads logs --cat"
    assert_fails "ads home" "No services"
}

test_service_but_no_root_givess_error() {
    go_test_project service-but-no-root
    cd service
    assert_fails "ads list" "within an ads project"
    assert_fails "ads up" "within an ads project"
    assert_fails "ads down" "within an ads project"
    assert_fails "ads home" "within an ads project"
}

test_nested_projects_and_services() {
    go_test_project interesting-hierarchy

    local top_listing="$(ads list)"
    assert_contains "$top_listing" "burger" "fries"
    assert_contains "$top_listing" "western"
        # Because nested services are allowed
    assert_not_contains "$top_listing" "pizza" "pepperoni"
        # Because nested projects form disjoint trees
    assert_contains "$top_listing" "all: burger, fries, western"
        # the default services
    assert_contains "$(ads home all)" "burger" "fries" "burger/western"
    assert_not_contains "$(ads home all)" "pizza" "pepperoni"

    cd burger
    local burger_listing="$(ads list)"
        # Should be exactly the same as the top level
    assert_contains "$top_listing" "burger" "fries"
    assert_contains "$top_listing" "western"
    assert_not_contains "$top_listing" "pizza" "pepperoni"
    assert_contains "$(ads home all)" "." "../fries" "western"
        # Home should be relative

    cd ../pizza
    local pizza_listing="$(ads list)"
    assert_contains "$pizza_listing" "pepperoni"
    assert_not_contains "$pizza_listing" "burger" "western" "fries"
        # Those are in the other project
    assert_not_contains "$pizza_listing" " pizza"
        # Because the root dir can't also be a service
        # (note space before pizza; the word "pizza" does occur
        # as the name of the root project; subprojects appear
        # in a list starting with space)
    assert_contains "$(ads home all)" "pepperoni"
}

source "$(dirname "${BASH_SOURCE[0]}")"/util/Framework.sh