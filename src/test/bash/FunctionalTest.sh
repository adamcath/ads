#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")"
readonly here="$(pwd)"

###############################################################################
# Helpers
###############################################################################

source "$here"/util/BashUnit.sh

ads() {
    python "$here"/../../main/python/ads.py "$@"
}

readonly test_tmp="$(mktemp -d /tmp/ads-test.XXX)"
copy_project_to_tmp_and_go() {
    local project_dir="$1"
    project_tmp="$(mktemp -d "$test_tmp"/"$(basename "$project_dir")".XXX)"
    if [[ "$(ls "$project_dir")" ]]; then
        cp -R "$project_dir"/* "$project_tmp"
    fi
    cd "$project_tmp"
}

readonly test_dir="$here"/..
go_test_project() {
    local name="$(basename "$1")"
    copy_project_to_tmp_and_go "$test_dir"/resources/"$name"
}

# Temporarily sets your ads profile to the value of stdin
set_ads_profile() {
    export ADS_PROFILE_HOME="$test_tmp"
    cat > "$test_tmp/.adsrc"
}

###############################################################################
# setup and teardown
###############################################################################

readonly regex_to_kill_between_tests="service.sh"

setup() {
    assert_not_running "$regex_to_kill_between_tests"
}

teardown() {
    procs_to_kill="$(pgrep -f "$regex_to_kill_between_tests" || true)"
    echo "$procs_to_kill" | xargs kill -9 &> /dev/null || true
    set_ads_profile << EOF
# empty default profile"
EOF
}

###############################################################################
# Basic happy cases
###############################################################################

test_trivial_service_basics() {
    go_test_project one-trivial-service

    assert_contains "$(ads list)" "A rather trivial service"

    assert_ok "ads up service" "Started service"
    assert_ok "ads status service" "service: ok"
    assert_contains "$(ads cat-logs)" \
        "some output from the service" "some errors from the service"

    assert_ok "ads down service" "Stopped service"
    assert_fails_with_stdout "ads status service" "service: not running"
    assert_contains "$(ads cat-logs)" \
        "some output from the service" "some errors from the service"
}

test_bogus_commands() {
    go_test_project one-trivial-service

    assert_fails "ads crap" "invalid choice"
}

test_idempotence() {
    go_test_project one-trivial-service

    assert_ok "ads up service" "Started"
    assert_ok "ads up service" "already running"

    assert_ok "ads down service" "Stopped"
    assert_ok "ads down service" "already stopped"
}

test_bounce() {
    go_test_project one-trivial-service

    assert_ok "ads up service"
    local old_service_pid="$(pgrep -f service.sh)"

    assert_ok "ads bounce service" "Stopped" "Started"
    local new_service_pid="$(pgrep -f service.sh)"

    assert_not_equal "$old_service_pid" "$new_service_pid"
}

test_logs() {
    go_test_project one-trivial-service

    ads up service
    ads logs service > /dev/null &

    sleep 1

    # There should be some invocation of "tail" with stdout and stderr
    # (the service's log files) as arguments
    assert_contains "$(ps -ef | grep 'tail -F')" "stdout" "stderr"

    pgrep -f "tail -F service/logs" | xargs kill -9
}

test_list_logs() {
    go_test_project one-trivial-service

    # Must start service to create log
    assert_ok "ads up service" "Started"

    # Use assert_equals instead of a contains check because this command
    # can be used for pipelining. So it must be _exactly_ a cwd-relative
    # list of paths.
    local log_list="$(ads list-logs)"
    assert_equal "$log_list" \
"service/logs/stdout
service/logs/stderr"

    # Path should be different from a different working directory
    cd service/logs
    local log_list="$(ads list-logs)"
    assert_equal "$log_list" \
"stdout
stderr"
}

###############################################################################
# Obscure project layouts
###############################################################################

test_empty_dir_gives_error() {
    go_test_project empty-dir
    assert_fails "ads list" "within an ads project"
    assert_fails "ads up" "within an ads project"
    assert_fails "ads down" "within an ads project"
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
        "None (add 'groups' to ~/.adsrc)" \
        "Default service" \
        "all"
    assert_fails_silently "ads list-logs"
    assert_fails_silently "ads cat-logs"
}

test_service_but_no_root_givess_error() {
    go_test_project service-but-no-root
    cd service
    assert_fails "ads list" "within an ads project"
    assert_fails "ads up" "within an ads project"
    assert_fails "ads down" "within an ads project"
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

    cd burger
    local burger_listing="$(ads list)"
        # Should be exactly the same as the top level
    assert_contains "$top_listing" "burger" "fries"
    assert_contains "$top_listing" "western"
    assert_not_contains "$top_listing" "pizza" "pepperoni"

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
}

###############################################################################
# Selectors
###############################################################################

test_interesting_selectors() {
    go_test_project interesting-selectors
    set_ads_profile << EOF
groups:
    europe:
    - ireland

default: north-america
EOF

    local north_america_status="$(ads status || true)"
    assert_contains "$north_america_status" "america" "canada"
    assert_not_contains "$north_america_status" "ireland"

    local europe_status="$(ads status europe || true)"
    assert_contains "$europe_status" "ireland"
    assert_not_contains "$europe_status" "america" "canada"

    local canada_status="$(ads status canada || true)"
    assert_contains "$canada_status" "canada"
    assert_not_contains "$canada_status" "america" "ireland"

    local listing="$(ads list)"
    assert_contains "$listing" \
        "north-america: america, canada" \
        "europe: ireland"
}

test_default_selector_is_all_when_none_defined() {
    go_test_project one-trivial-service

    assert_fails_with_stdout "ads status" "service"
}

###############################################################################
# main()
###############################################################################

run_tests