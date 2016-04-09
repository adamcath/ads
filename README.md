# Overview

Microservices are great, but running them on your dev box is annoying. Each one
has its own commands to start and stop, check status - and how are you supposed
to know where the logs are?

ads fixes this by requiring each participating service to expose a simple 
uniform interface for the most common commands: start, stop, status, and
log locations.

To use ads, drop a file called `ads.yml` in each service's directory:

```
start_cmd:
    gradle run > obscure/logs/dir/out &
    # ads can be used with any build system - cmds are just bash

stop_cmd:
    pgrep -f ninja-service | xargs kill -9
    # Still the most reliable way to kill a process

status_cmd:
    pgrep -f ninja-service
    # Exit status indicates whether any process matched

log_paths:
    - obscure/logs/dir/*
    - even/more/secret/logs/dir/**/ninja.log
    # Note the glob support
    
description: 
    Web service that turns your ordinary app into badass rockstart tech.
    # Optional but a good idea
```

There are more fields, but this will get you started.

Create one more file called `adsroot.yml`, in the root of your codebase:

```
# Actually, you don't need to put anything in it yet.
# The existence of the file is sufficient.
```

Now you can run ads from anywhere in the codebase and get at any of the services.

```
$ cd /anywhere/in/codebase
$ ads list
   ninja: Web service that turns your ordinary app into badass rockstart tech.
```

# A brief tour

You should follow along (see "Installing" first)
```
$ cd ads/docs/samples/intro
```

What do we got here?
```
$ ads list
All services in current project (intro):
     ninja: Slices and chops, mostly
        db: (No description)
    pirate: Walks the plank and shivers timbers
...
# We'll come back to the rest of this stuff
```

Let's start a service:
```
$ ads up -v ninja
--- Starting [ninja]
--- Checking if ninja is already running
cd /intro/./ninja
pgrep -f ninja.sh
--- Starting ninja
cd /intro/./ninja
mkdir logs
bash ninja.sh >logs/ninja.out 2>logs/ninja.err &
--- Started ninja
```

-v makes ads show you what it's doing. You can usually omit it.

Up is idempotent, so you don't have to remember what state it was in:
```
$ ads up -v ninja
--- Starting [ninja]
--- Checking if ninja is already running
cd /intro/./ninja
pgrep -f ninja.sh
4743
--- ninja is already running
```

Too much chopping; let's stop ninja:
```
$ ads down -v ninja
--- Checking if ninja is running
cd /intro/./ninja
pgrep -f ninja.sh
4863
--- Stopping ninja
cd /intro/./ninja
pgrep -f ninja.sh | xargs kill -9
--- Stopped ninja
```

I forget, is ninja up?
```
$ ads status -v ninja
cd /intro/./ninja
pgrep -f ninja.sh
--- ninja: not running
```

Any command can take a list of services:
```
$ ads up -v ninja pirate
--- Starting [ninja, pirate]
...
```

If you don't say which service, ads does 'em all (you can override this by setting 
`default` in adsroot.yml or ~/.ads_profile.yml):
```
$ ads status
--- db: not running
--- ninja: ok
--- pirate: ok
```

Let's tail the logs:
```
$ ads logs
cd /Users/arc/Projects/ads/doc/samples/intro
tail -F ninja/logs/ninja.err \
	ninja/logs/ninja.out \
	pirate/logs/treasure-chest/pirate.err \
	pirate/logs/treasure-chest/pirate.log

==> ninja/logs/ninja.err <==

==> ninja/logs/ninja.out <==
Chop!
Chop!

==> pirate/logs/treasure-chest/pirate.err <==

==> pirate/logs/treasure-chest/pirate.log <==
Arrrrr!
Arrrrr!
```

tail -F works pretty well with multiple log files, but if you want to 
focus on one, just specify the service.

The logs command has some cool variants:
```
$ ads help logs
usage: logs [-h] [--tail | --list | --cat] [--general | --errors]
            [service [service ...]]
...
  --tail      (Default) Follow the logs with tail -f
  --list      List the paths of all log files which exist (useful for
              pipelining)
  --cat       Dump the contents of all log files to stdout
```


# Getting started

### Dependencies

- ads has been tested with python 2.7.8 on Mac OS Yosemite-El Capitan
- python
- pip: install with `easy_install pip`
- shell stuff available on any Unixy OS (`find`, `bash`, `tail`, `cat`) 

### Installing from source

- `git clone https://github.com/adamcath/ads.git`
- `pip install -e .`

### Testing

- Go to an ads project (try doc/samples/intro) and type `ads list`
- Now try adding ads to your project by following the overview above

### Running the automated tests

- Get the source
- `./unit_tests.sh && ./functional_tests.sh`


# FAQ

#### My service needs some one-time setup before it runs. How do I tell ads this?

This is a common scenario; for example, you may need to set up the DB schema 
before you can start anything. ads doesn't have a solution for this yet. Your
service should probably try to detect the missing precondition, refuse to
start, and direct the user to the relevant wiki page.

#### Does ads have a concept of dependencies?

No. This is one area where ads is opinionated: in production, any service could
go down, and the other services would have to be able to deal with that.
The dependant service might go unhealthy, but it shouldn't crash. Therefore, 
starting in an arbitrary order is a special case of the general problem,
which you cannot avoid, of some services being up and others being down.

tl;dr: If a service can't run without another running, they're actually one service.

#### Can I specify a "build" step separate from "run"?

No. If running requires building, it should just do it. If that's slow, then
improve your project's build avoidance to reduce rebuilds.

#### Why isn't this just...
 
##### part of the build system?

- Building is a very general problem, and build systems are quite flexible.
  This flexibility comes at a cost: even in a well-factored build system, 
  you always have to figure out which targets you're supposed to run. 
  ads is a "run" system, not a build system, so it can be restricted to
  a fixed set of commands - the ones you need to run services. 
- Big projects often involve multiple languages and build systems.
  I wanted a uniform way to run them all.
- It's fairly annoying to implement things like `ads logs` in most build 
  systems. I wanted to make it trivial for developers to do the right thing.

##### an init.d script (or similar)?

ads is inspired by OS service managers, but:
- I don't want to "install" each service on my dev box. That would raise
  awkward questions about what happens when I change the code. I want
  to run things straight from source.
- init.d scripts are pretty fugly. Maybe other service managers are better;
  if so, I'd be curious to learn about them.
- I suspect that if this were a good solution, people would be doing it.

##### some project-specific helper scripts?

In my experience, code bases frequently evolve a set of helper scripts that 
make it tolerable to deal with multiple projects. They work well when there's 
one command to rule them all, but then somebody wants a way to _just restart my 
stuff_. Now you add some commands to just do that. It becomes very hard to
prevent spaghetti unless you end up designing something like ads, which lets
you freely compose commands with services. But then...you could have just 
used ads!

##### docker/vagrant/virtualization tech x?

Virtualization solves a very different set of problems - primarily service 
isolation. That said, I haven't tried docker yet (gasp!), so I'm not totally 
sure. I suspect ads will still make sense with docker (`ads up` would build and 
spin up a container). I'd love to hear your experiences with docker + ads, 
or if docker somehow making ads irrelevant.


# Advanced stuff

### groups

TODO write docs

### defaults

TODO write docs