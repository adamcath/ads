#!/usr/bin/env bash

test_edit() {
    go_test_project interesting-hierarchy

    # Hard to test launching a real editor. We just want to test that
    # ads home invokes $EDITOR path/to/first/ads.yml path/to/second/ads.yml,
    # which we can fake with cat
    EDITOR="cat" assert_ok "ads edit burger fries" \
        "started burger" "started fries"
}

source "$(dirname "${BASH_SOURCE[0]}")"/util/Framework.sh