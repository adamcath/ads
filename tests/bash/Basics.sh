#!/usr/bin/env bash

test_trivial_service_basics() {
    go_test_project one-trivial-service

    assert_contains "$(ads list)" "A rather trivial service"

    assert_ok "ads up service" "Starting service"
    assert_ok "ads status service" "service: ok"
    assert_contains "$(ads logs --cat)" \
        "some output from the service" "some errors from the service"

    assert_ok "ads down service" "Stopping service"
    assert_fails_with_stdout "ads status service" "service: not running"
    assert_contains "$(ads logs --cat)" \
        "some output from the service" "some errors from the service"
}

test_bogus_commands() {
    go_test_project one-trivial-service

    assert_fails "ads crap" "invalid choice"
}

test_idempotence() {
    go_test_project one-trivial-service

    assert_ok "ads up service" "Starting"
    assert_ok "ads up service" "already running"

    assert_ok "ads down service" "Stopping"
    assert_ok "ads down service" "already stopped"
}

test_bounce() {
    go_test_project one-trivial-service

    assert_ok "ads up service"
    local old_service_pid="$(pgrep -f service.sh)"

    assert_ok "ads bounce service" "Stopping" "Starting"
    local new_service_pid="$(pgrep -f service.sh)"

    assert_not_equal "$old_service_pid" "$new_service_pid"
}

test_up_verbose() {
    go_test_project one-trivial-service
    assert_not_contains "$(ads up)" 'Checking if' 'bash service.sh'
    assert_ok "ads down"
    assert_contains "$(ads up -v)" 'Checking if' 'bash service.sh'
    assert_ok "ads down"
    assert_contains "$(ads up --verbose)" 'Checking if' 'bash service.sh'
    assert_ok "ads down"

    # If up fails, show output even without -v
    go_test_project all-commands-fail
    assert_fails "ads up" 'Failed to start' 'bash service.sh'
}

test_down_verbose() {
    go_test_project one-trivial-service
    assert_ok "ads up"
    assert_not_contains "$(ads down)" 'Checking if' 'kill -9'
    assert_ok "ads up"
    assert_contains "$(ads down -v)" 'Checking if' 'kill -9'
    assert_ok "ads up"
    assert_contains "$(ads down --verbose)" 'Checking if' 'kill -9'

    # If down fails, show output even without -v
    go_test_project all-commands-fail
    assert_fails "ads up"
    assert_fails "ads down" 'Stop command failed' 'kill -9'
}

test_down_with_retries() {
    go_test_project leaky-stop-cmd
    export LEAKY_STOP_SLEEP=1
    assert_ok "ads up"
    assert_ok "ads down -v" "retry"

    # Without retries, we'd see that status still showed true
    assert_contains "$(ads status)" "not running"
}

# Disabled because I noticed it's flaky
#test_down_but_retries_time_out() {
#    go_test_project leaky-stop-cmd
#    export LEAKY_STOP_SLEEP=100
#    assert_ok "ads up"
#    assert_fails "ads down -v" "is still running"
#
#    # Ok, actually kill it (clean up)
#    export LEAKY_STOP_SLEEP=0
#    assert_ok "ads down"
#}

test_bounce_verbose() {
    go_test_project one-trivial-service
    assert_ok "ads up"
    assert_not_contains "$(ads bounce)" 'kill -9' 'bash service.sh'
    assert_ok "ads up"
    assert_contains "$(ads bounce -v)" 'kill -9' 'bash service.sh'
    assert_ok "ads up"
    assert_contains "$(ads bounce --verbose)" 'kill -9' 'bash service.sh'

    # If up fails, show output even without -v
    go_test_project all-commands-fail
    assert_ok "ads up"
    assert_fails "ads bounce" \
        'Stop command failed' 'kill -9' \
        'Failed to start' 'bash service.sh'
}

test_bounce_with_retries() {
    go_test_project leaky-stop-cmd
    export LEAKY_STOP_SLEEP=1
    assert_ok "ads up"

    # Without retries, this would fail seeing that it's still running
    assert_ok "ads bounce"
}

test_status_verbose() {
    go_test_project one-trivial-service

    assert_not_contains "$(ads status)" 'Checking if' "pgrep"
    assert_contains "$(ads status -v)" 'Checking if' "pgrep"
    assert_contains "$(ads status --verbose)" 'Checking if' "pgrep"
}

source "$(dirname "${BASH_SOURCE[0]}")"/util/Framework.sh