###################################################
# Helpers
###################################################

_bunit_exit_hook() {
    echo "+---------------------------------------------------------FAILED-+"
}

_bunit_print_frame() {
    line="$1"
    func="$2"
    file="$3"
    printf "! %s() (%s:%d)\n" "$func" "$(basename "$file")" "$line"
}

_bunit_print_stack_trace() {
    i=1
    while frame="$(caller "$i")"; do
        ((i++))
        _bunit_print_frame $frame
    done
}

_bunit_sub_newlines() {
    echo -e "$1"
    #printf "%s" "$1" | tr '\n' '|'
}

_bunit_assert_containment() {
    should_contain="$1"
    haystack="$2"
    shift 2
    needles=("$@")

    if [[ "${#needles[@]}" == 0 ]]; then
        return
    fi

    for needle in "${needles[@]}"; do
        local match
        if [[ "$haystack" == *"$needle"* ]]; then
            match=true
        else
            match=false
        fi

        haystack_clean="$(_bunit_sub_newlines "$haystack")"
        if [[ "$match" != "$should_contain" ]]; then
            if [[ "$should_contain" == true ]]; then
                fail "\"$haystack_clean\" does not contain \"$needle\""
            else
                fail "\"$haystack_clean\" contains \"$needle\" (but should not)"
            fi
        fi
    done
}

###################################################
# Public API
###################################################

run_tests() {
    local all_tests=( $(declare -F | awk '{print $3}' | grep "^test") )

    trap '_bunit_exit_hook' EXIT

    for test in ${all_tests[@]}; do
        echo
        echo "+----------------------------------------------------------------+"
        echo "| $test"


        if [[ $(type -t setup) == "function" ]]; then
            setup
        fi

        "$test" # If it fails, exit hook will be called
        echo "+---------------------------------------------------------PASSED-+"

        if [[ $(type -t teardown) == "function" ]]; then
            teardown
        fi

    done

    trap - EXIT

    echo
    echo "TESTS COMPLETE! Passed: ${#all_tests[*]}"
}

###################################################
# assertions

fail() {
    echo -e "FAILED: $1" 1>&2
    _bunit_print_stack_trace
    exit 17
}

assert_contains() {
    _bunit_assert_containment true "$@"
}

assert_not_contains() {
    _bunit_assert_containment false "$@"
}

assert_ok() {
    cmd="$1"
    if ! output="$($1)"; then
        fail "command \"$1\" failed"
    fi
    echo "$output"
    shift
    assert_contains "$output" "$@"
}

assert_fails() {
    cmd="$1"
    if stderr="$($1 2>&1 1>/dev/null)"; then
        fail "command \"$1\" succeeded (but should have failed)"
    fi
    echo "$stderr"
    shift
    assert_contains "$stderr" "$@"
}

assert_fails_silently() {
    cmd="$1"
    if both_outputs="$($1 2>&1)"; then
        fail "command \"$1\" succeeded (but should have failed)"
    fi
    if [[ -e "$both_outputs" ]]; then
        fail "command \"$1\" should have had no output, but had: \
                $(_bunit_sub_newlines "$both_outputs")"
    fi
}

assert_fails_with_stdout() {
    cmd="$1"
    if output="$($1)"; then
        fail "command \"$1\" succeeded (but should have failed)"
    fi
    echo "$output"
    shift
    assert_contains "$output" "$@"
}

assert_equal() {
    if [[ "$1" != "$2" ]]; then
        fail "\"$(_bunit_sub_newlines "$1")\" != \"$(_bunit_sub_newlines "$2")\""
    fi
}

assert_not_equal() {
    if [[ "$1" == "$2" ]]; then
        fail "\"$(_bunit_sub_newlines "$1")\" == \"$(_bunit_sub_newlines "$2")\""
    fi
}

assert_not_running() {
    pgrep_term="$1"
    if pgrep -f "$pgrep_term" > /dev/null; then
        ps_output="$(ps -ef | grep "$pgrep_term")"
        fail "These processes should not be running:\n$ps_output"
    fi
}