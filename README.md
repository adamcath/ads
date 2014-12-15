# Overview

Microservices are great, but running them on your dev box is annoying. Each one
has its own commands to start and stop, check status...and how are you supposed
to know where the logs are?

ads addresses this problem by requiring each participating service to expose a
simple uniform interface for the most common commands: start, stop, status, and
log locations.

To use ads, drop a file called "ads.yml" in each service's directory:

```
description: 
    Web service that turns your ordinary app into badass rockstart tech.

start:
    gradle run > obscure/logs/dir/out &
    # ads can be used with any build system -- it's just bash

stop:
    pgrep -f ninja-service | xargs kill -9
    # Still the most reliable way to kill a process

status:
    pgrep -f ninja-service
    # Exit status indicates whether any process matched

logs:
    - obscure/logs/dir/*
    - even/more/secret/logs/dir/ninja.log
    # List any files with interesting output. Note the glob support
```

And one more, called "adsroot.yml", in the root of your codebase:

```
# Actually, there's nothing to put here yet.
# The existence of the file is sufficient.
```

Now you can run ads from anywhere in the codebase and get at any of the services.

```
~/codebase/ninja $ ads list
   ninja: Web service that turns your ordinary app into badass rockstart tech.
  io-tld: Converts a domain into the domain of a company which is crushing it.
webscale: (No description)
```

# Starting a single service

```
~/codebase/ninja $ ads up ninja
cd ~/codebase/ninja
gradle run > obscure/logs/dir/out &
--- Started ninja-service

# up is idempotent
~/codebase/ninja $ ads up ninja
--- ninja-service is already running
```

# Stopping a single service

```
~/codebase/ninja $ ads down ninja
cd ~/codebase/ninja
pgrep -f ninja-service | xargs kill -9
--- Stopped ninja-service
```

# Following logs

```
~/codebase/ninja $ ads logs   # You could specify a service; default is all
tail -F ~/codebase/ninja/obscure/logs/dir/out ~/codebase/webscale/logs/webscale.log

==> ~/codebase/ninja/obscure/logs/dir/out <==
some log lines from ninja
and a few more
etc etc

==> ~/codebase/webscale/logs/webscale.log <==
tail will just switch to the other log file when somebody writes to it

...
```

# Prerequisites

- python: ads has been tested with 2.7.8 on Mac
