``` .__   __  .__       .__
  _____  __ __|  |_/  |_|__|_____ |  |   ____ ___  ___
 /     \|  |  \  |\   __\  \____ \|  | _/ __ \\  \/  /
|  Y Y  \  |  /  |_|  | |  |  |_> >  |_\  ___/ >    <
|__|_|  /____/|____/__| |__|   __/|____/\___  >__/\_ \
      \/                   |__|             \/      \/
```

[![CI](https://github.com/sst/multiplex/actions/workflows/ci.yml/badge.svg)](https://github.com/sst/multiplex/actions/workflows/ci.yml)

**Multiplex** is a command-line multiplexer along with a simple Python
API to run multiple processes in parallel and stop them all at once, or
based on some condition.

Multiplex will gracefully shutdown child processes, and multiplex their
output and error streams to stdout and stderr in a way that is easily
parsable with regular command line tools.

Multiplex is useful when you need to run multiple programs all at once
and combine their output. For instance, you need a webserver, a
workqueue and a database to run standalone all together. You could write
a shell script, or you could write a one liner using `multiplex`.

Here's how you'd benchmark Python's embedded HTTP server with a
one-liner using the new dependency format:

```
# Starts a web server, waits 2s and start the benchmark, and terminates after that
multiplex "SERVER|silent=python3 -m http.server" "+2s|end=ab -n1000 http://localhost:8000/"
```

Multiplex is designed to be run as a CLI tool, without the need of a
configuration file -- pass in arguments to define the behaviour that you want.

Compared to other tools like *foreman* or *overmind*, multiplex offers a compact
expressive syntax to define the orchestration of your processes, and a full
Python API if you want to have more advanced use cases.

# Installing

Multiplex is available on PyPI at https://pypi.org/project/multiplex-sh

With `uv`

    $ uv tool install multiplex-sh
    $ multiplex --help

Using `pip`

    $ pip install multiplex-sh
    $ multiplex --help

Straight from Github:

    $ curl -o multiplex https://raw.githubusercontent.com/sebastien/multiplex/main/src/py/multiplex.py; chmod +x multiplex
    $ ./multiplex --help

Note that you'll need a Python 3.8+ interpreter available, and that this is
only tested on Linux and MacOS.

# Usage

## Commands

Here are some example commands that will help understand the syntax:

Running multiple commands in parallel:

```bash
multiplex "python -m http.server -p 8000" "python -m http.server -p 8001"
```

Running a command after 5s delay:

```bash
multiplex "+5=python -m http.server"
```

Running a command after another completes:

```bash
multiplex "A=find . -name '*.*'" "B:A=du -hs ."
```

Running multiple commands with complex coordination:

```bash
# Starts the DB, wait two seconds after it started, run the server, and
# once the server is started, start the test. When the test ends,
# gracefully shut down everything.
multiplex "DB=mongod" "API:DB&+2=node server.js" ":API&|end=npm test"
```

## Command Syntax

Commands follow a structured format:

```
[KEY][#COLOR][+DELAY…][:DEP…][|ACTIONS]=COMMAND`
```

where:

- `#COLOR` for a given color, either by name or in hex
- `:DEP` is a dependency (see below, can be chained)
- `|ACTION` is an action (can be chained)

Dependencies are in the following form:

```
[KEY][&][+DELAY…]
```

- `KEY` for the process name we wait on, if it is followed by `&` then it
  indicates the process start instead of the end.
- `+DELAY` for a delay (can be chained)

**Channel name** (`KEY=`): Assign a name to a process for reference by other commands. The format is
`KEY=command` where `KEY` is alphanumeric (`A-Z`, `a-z`, `0-9`, `_`):
- `A=python -m http.server`
- `DB=mongod --port 27017`
- `API_SERVER=node app.js`

**Colors** (`#COLOR`): Style channel names with colors in output. Can take
named colors `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `bright_red`, `bright_green`, or
6-digit **hex codes** like `FF0000`:
- `server#red=python -m http.server`
- `db#blue=mongod --port 27017`
- `worker#00FF00=python worker.py`
- `logs#FFA500=tail -f app.log`

**Delays** (`+DELAY`): Delay the start of a command by a specified time. Format
is `+DELAY` where DELAY can be a number (seconds) or include time units, like
`ms` (milliseconds), `s` (seconds), `m` (minutes) ― units are optional,
defaults to seconds:

- **Time unit suffixes**: `ms` (milliseconds), `s` (seconds), `m` (minutes) - units are optional, defaults to seconds
- **Plain numbers**: `5`, `1.5`, `0.5` (treated as seconds)
- **Complex combinations**: `1m30s`, `2s500ms`, `1m1s1ms`
- **Multiple delays**: `+1+0.5` (applies 1s delay, then 0.5s delay)

And some examples:

- `+2=command` ― start after 2 seconds
- `API+1.5=command` ― start API after 1.5 seconds
- `#blue+500ms=command` ― start with blue color after 500 milliseconds
- `WORKER#green+2:DB=command` ― start `WORKER` (green) after 2 seconds, then wait for DB

## Dependencies (`:DEP`)

Dependencies allow commands to wait for other processes and apply delays.
Each dependency follows: `[KEY][&][+DELAY…]`, where:

- **`KEY`**: Process name to wait for
- **`&`**: Optional indicator to wait for process **start** instead of **end**
- **`+DELAY`**: Optional delays to apply after the dependency condition is met

Here are some more examples:

- **End dependency**: `:A` ― wait for process A to complete
- **Start dependency**: `:A&` ― wait for process A to start
- **Delayed dependency**: `:A+1s` ― wait for A to complete, then wait 1 second
- **Start with delay**: `:A&+500ms` ― wait for A to start, then wait 500ms

Dependencies can be chained like `:DEP1:DEP2:DEP3`, some examples:

- `:A:B` ― wait for both A and B to complete
- `:A&:B+1s` ― wait for A to start AND B to complete + 1s
- `:DB:CACHE&+2s:CONFIG` ― wait for DB to end, CACHE to start + 2s, and CONFIG to end

Delays are like previously mentioned:
- `:A+2` ― wait for A, then 2 seconds
- `:A+500ms` ― wait for A, then 500 milliseconds
- `:B&+1m30s` ― wait for B to start, then 90 seconds
- `:C+1+0.5` ― wait for C, then 1s, then 0.5s more

### Actions (`|ACTION`)

Actions modify process behavior:

- `|end` ― When this process ends, terminate all other processes
- `|silent` ― Suppress all output (stdout and stderr)
- `|noout` ― Suppress stdout only
- `|noerr` ― Suppress stderr only

Actions can be combined: `|silent|end=command`

### Examples by Pattern

Sequential execution:

```bash
# Builds and runs once the build finishes.
multiplex "BUILD=npm run build" ":BUILD=npm start"
```

Parallel with start delays:

```bash
multiplex "DB=database" "API+2=api-server" "UI+3=ui-server"
```

Mixed start delays and dependencies:

```bash
multiplex "DB+1=database" "API+2:DB=api-server" "UI+0.5:API&=ui-server"
```

Parallel with coordination:

```bash
multiplex "DB=mongod" "API:DB+2=node server.js" ":API&=npm test"
```

Complex dependency chain:

```bash
multiplex "CONFIG=setup" "DB:CONFIG+1=database" "CACHE:CONFIG+0.5=redis" "API:DB:CACHE&+2=server"
```

Development environment:

```bash
multiplex "DB=mongod" "API:DB+2=npm run dev" "UI:API&+1=npm run ui" ":UI&+5=open http://localhost:3000"
```

Special Cases: if your command contains an equals sign, use an empty prefix:

```bash
multiplex "=echo a=b"
```

### CLI

Options:
- `-t|--timeout SECONDS`, terminate all processes after specified time.
- `--time`, add timestamps to log entries as (HH:MM:SS)
- `--time=relative`, show relative timestamps (00:00:00 start)

Output:

```bash
# Without timestamps
$│A│echo hello from A
<│A│hello from A
=│A│0

# With absolute timestamps (--timestamp)
12:31:20|$│A│echo hello from A
12:31:20|<│A│hello from A
12:31:21|=│A│0

# With relative timestamps (--timestamp -r)
00:00:00|$│A│echo hello from A
00:00:00|<│A│hello from A
00:00:01|=│A│0
```

# Examples

The [examples/](examples/) directory contains practical demonstrations of multiplex features. Each example is a runnable script that showcases specific functionality:

## Basic Patterns

**Sequential Build** ([`examples/sequential-build.sh`](examples/sequential-build.sh))
```bash
multiplex "BUILD=echo 'Building...'" ":BUILD=echo 'Starting...'"
```
Simple dependency chain where one command waits for another to complete.

**Process Dependencies** ([`examples/process-delays.sh`](examples/process-delays.sh))
```bash
multiplex "STEP1=echo 'init'" "STEP2:STEP1=echo 'process'" ":STEP2=echo 'done'"
```
Demonstrates sequential execution where each process waits for the previous one.

**Time Delays** ([`examples/time-delays.sh`](examples/time-delays.sh))
```bash
multiplex "INIT=echo 'starting'" "+2=echo 'after 2 seconds'" "+5=echo 'after 5 seconds'"
```
Shows simple time-based delays for process coordination.

**Parallel Coordination** ([`examples/parallel-coordination.sh`](examples/parallel-coordination.sh))
```bash
multiplex "DB=database" "API+2=api-server" "UI+2=ui-server" "+5=open-browser"
```
Multiple services starting in parallel with staggered delays.

## Advanced Dependency Management

**Dependencies Demo** ([`examples/dependencies-demo.sh`](examples/dependencies-demo.sh))
```bash
# Complex dependency chains with start/end dependencies and delays
multiplex "DB#blue=sleep 2 && echo 'Database: Ready'" \
          "API#green:DB=sleep 1 && echo 'API: Connected'" \
          "UI#cyan:API=echo 'UI: Ready'" \
          ":UI=echo 'All services ready!'"
```
Comprehensive demonstration of the dependency system with:
- End dependencies (`:DB` - wait for DB to complete)
- Start dependencies (`:API&` - wait for API to start)
- Delayed dependencies (`:DB+1s` - wait for DB + 1 second)
- Multiple dependencies (`:DB:CACHE&+2s`)

**Development Environment** ([`examples/dev-environment.sh`](examples/dev-environment.sh))
```bash
multiplex "DB=echo 'MongoDB starting...'; sleep 2; echo 'MongoDB ready'" \
          "API+2=echo 'API starting...'; sleep 1; echo 'API ready'" \
          "UI+2=echo 'UI starting...'; sleep 1; echo 'UI ready'" \
          "+5=echo 'Opening browser...'"
```
Realistic development environment setup with proper service coordination.

## Timing and Precision

**Delay Suffixes Demo** ([`examples/delay-suffixes-demo.sh`](examples/delay-suffixes-demo.sh))
```bash
multiplex "echo 'Starting...'" \
          "+100ms=echo 'Quick response'" \
          "+2s=echo 'After 2 seconds'" \
          "+1m=echo 'One minute later'" \
          "+1m30s750ms=echo 'Complex timing (90.75s)'"
```
Demonstrates advanced timing features:
- Milliseconds (`100ms`, `750ms`)
- Seconds (`2s`, `30s`)
- Minutes (`1m`)
- Complex combinations (`1m30s750ms`)

**Timestamp Demo** ([`examples/timestamp-demo.sh`](examples/timestamp-demo.sh))
```bash
multiplex --timestamp -r "A=echo hello" "B+1s=echo world"
```
Shows timestamp functionality with relative timing display.

## Visual and Output Control

**Color Demo** ([`examples/color-demo.sh`](examples/color-demo.sh))
```bash
multiplex "server#red=python -m http.server" \
          "worker#00FF00=python worker.py" \
          "monitor#cyan=system-monitor" \
          "logs#FFA500=tail -f app.log"
```
Demonstrates color functionality:
- Named colors (`red`, `blue`, `green`, `cyan`, `yellow`, `magenta`, `white`)
- Bright colors (`bright_red`, `bright_green`, etc.)
- Hex colors (`00FF00` for bright green, `FFA500` for orange)

**Actions Demo** ([`examples/actions-demo.sh`](examples/actions-demo.sh))
```bash
multiplex "SERVER|silent=long-running-process" \
          "+1=echo 'Running tests...'" \
          "+2|end=echo 'Tests complete - terminating all'"
```
Shows process actions:
- `|silent` - suppress all output
- `|noout` - suppress stdout only
- `|noerr` - suppress stderr only
- `|end` - terminate all processes when this one ends

**Redirects Demo** ([`examples/redirects-demo.sh`](examples/redirects-demo.sh))
Advanced output redirection and file handling examples.

## Real-world Use Cases

**HTTP Benchmark** ([`examples/http-benchmark.sh`](examples/http-benchmark.sh))
```bash
multiplex "A=python3 -m http.server" ":A=ab -n1000 http://localhost:8000/"
```
Start a web server and run Apache Bench against it once it's ready.

**CI/CD Pipeline** ([`examples/cicd-pipeline.sh`](examples/cicd-pipeline.sh))
```bash
multiplex "BUILD=npm run build" ":BUILD=npm test" ":TEST=npm run deploy|end"
```
Sequential build, test, and deployment pipeline.

**Special Cases** ([`examples/special-cases.sh`](examples/special-cases.sh))
```bash
multiplex "=echo 'VAR=value'" "SETUP|silent=configuration" ":SETUP=continue"
```
Handles edge cases like commands with equals signs and complex action combinations.

**Complete Demo** ([`examples/complete-demo.sh`](examples/complete-demo.sh))
```bash
multiplex "SETUP|silent=init" "DB+1=database" "API:DB=server" "UI:API=frontend" ":UI|end=done"
```
Comprehensive example showcasing all major features together.

## Running Examples

All examples can be run directly:

```bash
# Run any example script
./examples/dependencies-demo.sh

# Or run the underlying multiplex command
python3 -m multiplex "DB=echo 'Database ready'" ":DB=echo 'App started'"
```

Each example includes explanatory comments and demonstrates specific multiplex features in isolation or combination.

## Related tools

- [foreman](https://github.com/ddollar/foreman) and [honcho](https://github.com/nickstenning/honcho)
  allows to start and manage processes defined in a `Procfile`. Compared to foreman,
  multiplex can be run from the CLI directly without a supporting file and offers
  more flexibility in orchestrating the processes.

- [mprocs](https://github.com/pvolok/mprocs) runs multiple processes in parallel, and provides
  a TUI to navigate between each.
