#!/usr/bin/env bash

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

source "$(dirname "${BASH_SOURCE[0]}")"/util/Framework.sh