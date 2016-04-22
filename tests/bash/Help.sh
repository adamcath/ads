#!/usr/bin/env bash

test_main_help() {
    assert_fails ads
    assert_contains "$(ads)" 'manage microservices'
    assert_equal "$(ads -h)" "$(ads)"
    assert_equal "$(ads -h)" "$(ads --help)"
    assert_equal "$(ads -h)" "$(ads help)"
}

test_cmd_helps() {
    assert_ok 'ads help help' 'Display help about ads'
    assert_ok 'ads help list' 'Print the list of available service'
    assert_ok 'ads help up' 'Ensure the specified services are running'
    assert_ok 'ads help down' 'Ensure the specified services are not running'
    assert_ok 'ads help bounce' 'Stop and restart the specified services'
    assert_ok 'ads help status' 'Print status of the specified services'
    assert_ok 'ads help logs' 'Tail the logs of the specified services'
    assert_ok 'ads help home' 'Print paths to the specified services'
    assert_ok 'ads help edit' 'Edit a service'

    assert_equal "$(ads help start)" "$(ads help up)"
    assert_equal "$(ads help run)" "$(ads help up)"
    assert_equal "$(ads help stop)" "$(ads help down)"
    assert_equal "$(ads help kill)" "$(ads help down)"
    assert_equal "$(ads help restart)" "$(ads help bounce)"
}

source "$(dirname "${BASH_SOURCE[0]}")"/util/Framework.sh