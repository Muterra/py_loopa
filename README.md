# What is Loopa?

<!-- [![Build Status](https://travis-ci.org/Muterra/py_daemoniker.svg?branch=master)](https://travis-ci.org/Muterra/py_daemoniker)
[![Build status](https://ci.appveyor.com/api/projects/status/h07tux1oop0gw989?svg=true&passingText=Windows%20-%20👍&pendingText=Windows%20-%20pending&failingText=master%20-%20👎)](https://ci.appveyor.com/project/Badg/py-daemoniker) -->

Loopa is a pure-Python framework for building Arduino-like apps and utilities
on top of the built-in ```asyncio``` library. It runs on any event loop, and
automatically handles event loop closure and, if necessary, threaded operation.

Loopa also contains various utilities for event loop coordination.

<!-- **Full documentation is available [here](https://daemoniker.readthedocs.io/en/latest/).** -->

## Installing

Daemoniker requires **Python 3.5** or higher.

```
    pip install loopa
```

# Example usage
    
<!-- At the beginning of your script, invoke daemonization through the
``daemoniker.Daemonizer`` context manager:

```python
    from daemoniker import Daemonizer
    
    with Daemonizer() as (is_setup, daemonizer):
        if is_setup:
            # This code is run before daemonization.
            do_things_here()
            
        # We need to explicitly pass resources to the daemon; other variables
        # may not be correct    
        is_parent, my_arg1, my_arg2 = daemonizer(
            path_to_pid_file, 
            my_arg1, 
            my_arg2
        )
        
        if is_parent:
            # Run code in the parent after daemonization
            parent_only_code()
    
    # We are now daemonized, and the parent just exited.
    code_continues_here()
```
    
Signal handling works through the same ``path_to_pid_file``:

```python
    from daemoniker import SignalHandler1
    
    # Create a signal handler that uses the daemoniker default handlers for
    # ``SIGINT``, ``SIGTERM``, and ``SIGABRT``
    sighandler = SignalHandler1(path_to_pid_file)
    sighandler.start()
    
    # Or, define your own handlers, even after starting signal handling
    def handle_sigint(signum):
        print('SIGINT received.')
    sighandler.sigint = handle_sigint
```
    
These processes can then be sent signals from other processes:

```python
    from daemoniker import send
    from daemoniker import SIGINT
    
    # Send a SIGINT to a process denoted by a PID file
    send(path_to_pid_file, SIGINT)
``` -->

# Contributing

Help is welcome and needed. Unfortunately we're so under-staffed that we haven't even had time to make a thorough contribution guide. In the meantime:

## Guide

+ Issues are great! Open them for anything: feature requests, bug reports, etc. 
+ Fork, then PR.
+ Open an issue for every PR.
  + Use the issue for all discussion.
  + Reference the PR somewhere in the issue discussion.
+ Please be patient. We'll definitely give feedback on anything we bounce back to you, but especially since we lack a contribution guide, style guide, etc, this may be a back-and-forth process.
+ Please be courteous in all discussion.

## Project priorities

+ Contribution guide
+ Code of conduct

## Sponsors and backers

If you like what we're doing, please consider [sponsoring](https://opencollective.com/golix#sponsor) or [backing](https://opencollective.com/golix) Muterra's open source collective.

**Sponsors**

  <a href="https://opencollective.com/golix/sponsors/0/website" target="_blank"><img src="https://opencollective.com/golix/sponsors/0/avatar"></a>
  <a href="https://opencollective.com/golix/sponsors/1/website" target="_blank"><img src="https://opencollective.com/golix/sponsors/1/avatar"></a>
  <a href="https://opencollective.com/golix/sponsors/2/website" target="_blank"><img src="https://opencollective.com/golix/sponsors/2/avatar"></a>
  <a href="https://opencollective.com/golix/sponsors/3/website" target="_blank"><img src="https://opencollective.com/golix/sponsors/3/avatar"></a>
  <a href="https://opencollective.com/golix/sponsors/4/website" target="_blank"><img src="https://opencollective.com/golix/sponsors/4/avatar"></a>

-----

**Backers**

  <a href="https://opencollective.com/golix/backers/0/website" target="_blank"><img src="https://opencollective.com/golix/backers/0/avatar"></a>
  <a href="https://opencollective.com/golix/backers/1/website" target="_blank"><img src="https://opencollective.com/golix/backers/1/avatar"></a>
  <a href="https://opencollective.com/golix/backers/2/website" target="_blank"><img src="https://opencollective.com/golix/backers/2/avatar"></a>
  <a href="https://opencollective.com/golix/backers/3/website" target="_blank"><img src="https://opencollective.com/golix/backers/3/avatar"></a>
  <a href="https://opencollective.com/golix/backers/4/website" target="_blank"><img src="https://opencollective.com/golix/backers/4/avatar"></a>
  <a href="https://opencollective.com/golix/backers/5/website" target="_blank"><img src="https://opencollective.com/golix/backers/5/avatar"></a>
  <a href="https://opencollective.com/golix/backers/6/website" target="_blank"><img src="https://opencollective.com/golix/backers/6/avatar"></a>
  <a href="https://opencollective.com/golix/backers/7/website" target="_blank"><img src="https://opencollective.com/golix/backers/7/avatar"></a>
  <a href="https://opencollective.com/golix/backers/8/website" target="_blank"><img src="https://opencollective.com/golix/backers/8/avatar"></a>
  <a href="https://opencollective.com/golix/backers/9/website" target="_blank"><img src="https://opencollective.com/golix/backers/9/avatar"></a>
  <a href="https://opencollective.com/golix/backers/10/website" target="_blank"><img src="https://opencollective.com/golix/backers/10/avatar"></a>
  <a href="https://opencollective.com/golix/backers/11/website" target="_blank"><img src="https://opencollective.com/golix/backers/11/avatar"></a>
  <a href="https://opencollective.com/golix/backers/12/website" target="_blank"><img src="https://opencollective.com/golix/backers/12/avatar"></a>
  <a href="https://opencollective.com/golix/backers/13/website" target="_blank"><img src="https://opencollective.com/golix/backers/13/avatar"></a>
  <a href="https://opencollective.com/golix/backers/14/website" target="_blank"><img src="https://opencollective.com/golix/backers/14/avatar"></a>
  <a href="https://opencollective.com/golix/backers/15/website" target="_blank"><img src="https://opencollective.com/golix/backers/15/avatar"></a>
  <a href="https://opencollective.com/golix/backers/16/website" target="_blank"><img src="https://opencollective.com/golix/backers/16/avatar"></a>
  <a href="https://opencollective.com/golix/backers/17/website" target="_blank"><img src="https://opencollective.com/golix/backers/17/avatar"></a>
  <a href="https://opencollective.com/golix/backers/18/website" target="_blank"><img src="https://opencollective.com/golix/backers/18/avatar"></a>
  <a href="https://opencollective.com/golix/backers/19/website" target="_blank"><img src="https://opencollective.com/golix/backers/19/avatar"></a>
  <a href="https://opencollective.com/golix/backers/20/website" target="_blank"><img src="https://opencollective.com/golix/backers/20/avatar"></a>
  <a href="https://opencollective.com/golix/backers/21/website" target="_blank"><img src="https://opencollective.com/golix/backers/21/avatar"></a>
  <a href="https://opencollective.com/golix/backers/22/website" target="_blank"><img src="https://opencollective.com/golix/backers/22/avatar"></a>
  <a href="https://opencollective.com/golix/backers/23/website" target="_blank"><img src="https://opencollective.com/golix/backers/23/avatar"></a>
  <a href="https://opencollective.com/golix/backers/24/website" target="_blank"><img src="https://opencollective.com/golix/backers/24/avatar"></a>
  <a href="https://opencollective.com/golix/backers/25/website" target="_blank"><img src="https://opencollective.com/golix/backers/25/avatar"></a>
  <a href="https://opencollective.com/golix/backers/26/website" target="_blank"><img src="https://opencollective.com/golix/backers/26/avatar"></a>
  <a href="https://opencollective.com/golix/backers/27/website" target="_blank"><img src="https://opencollective.com/golix/backers/27/avatar"></a>
  <a href="https://opencollective.com/golix/backers/28/website" target="_blank"><img src="https://opencollective.com/golix/backers/28/avatar"></a>
  <a href="https://opencollective.com/golix/backers/29/website" target="_blank"><img src="https://opencollective.com/golix/backers/29/avatar"></a>