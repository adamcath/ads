#!/usr/bin/env bash

test_logs_default() {
    # Same as logs --tail
    go_test_project one-trivial-service

    # Start service to create logs
    ads up service

    local logs_output="$(mktemp)"

    ads logs service > "$logs_output" &
    local pid="$!"
    sleep 1
    echo "Looking for expected tail output"
    grep "==> service/logs/stdout <==" "$logs_output"
    grep "==> service/logs/stderr <==" "$logs_output"
    kill -9 "$pid"

    # tail args are cwd-relative
    cd service/logs
    ads logs service > "$logs_output" &
    local pid="$!"
    sleep 1
    echo "Looking for expected tail output"
    grep "==> stdout <==" "$logs_output"
    grep "==> stderr <==" "$logs_output"
    kill -9 "$pid"
}

test_logs_tail() {
    test_logs_default
}

test_list_logs() {
    go_test_project one-trivial-service

    # Must start service to create log
    assert_ok "ads up service"
    sleep 1

    # Use assert_equal instead of a contains check because this command
    # can be used for pipelining. So it must be _exactly_ a cwd-relative
    # list of paths.
    local log_list="$(ads logs --list)"
    assert_equal "$log_list" \
"service/logs/stdout
service/logs/stderr"

    # Path should be different from a different working directory
    cd service/logs
    local log_list="$(ads logs --list)"
    assert_equal "$log_list" \
"stdout
stderr"
}

test_cat_logs() {
    go_test_project one-trivial-service

    # Start service to create logs
    ads up service
    sleep 1

    # ads logs cat actually prints the cat command
    assert_contains \
        "$(ads logs --cat service)" \
        "cat service/logs/stdout service/logs/stderr"

    # cat args are cwd-relative
    cd service/logs
    assert_contains \
        "$(ads logs --cat service)" \
        "cat stdout stderr"
}

test_logs_commands_when_logs_missing() {
    go_test_project one-trivial-service

    assert_fails "ads logs --list" "No general log files found"
    assert_fails "ads logs --cat" "No general log files found"
}

test_logs_commands_when_some_logs_missing() {
    go_test_project interesting-hierarchy

    touch burger/burger.log

    assert_ok "ads logs --list" "burger.log"
    assert_ok "ads logs --cat" "burger.log"
}

test_general_vs_error_logs() {
    go_test_project one-trivial-service

    assert_ok "ads up"

    # --general and --errors are disjoint
    local logs_listing="$(ads logs --list --general)"
    assert_contains "$logs_listing" "stdout" "stderr"
    assert_not_contains "$logs_listing" "other_err"

    local errors_listing="$(ads logs --list --errors)"
    assert_contains "$errors_listing" "stderr" "other_err"
    assert_not_contains "$errors_listing" "stdout"

    # Default is --general
    assert_equal "$(ads logs --list)" "$(ads logs --list --general)"
}

source "$(dirname "${BASH_SOURCE[0]}")"/util/Framework.sh