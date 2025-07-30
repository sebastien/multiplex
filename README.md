``` 
              .__   __  .__       .__
  _____  __ __|  |_/  |_|__|_____ |  |   ____ ___  ___
 /     \|  |  \  |\   __\  \____ \|  | _/ __ \\  \/  /
|  Y Y  \  |  /  |_|  | |  |  |_> >  |_\  ___/ >    <
|__|_|  /____/|____/__| |__|   __/|____/\___  >__/\_ \
      \/                   |__|             \/      \/
```

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

    multiplex "SERVER|silent=python -m http.server" ":SERVER&+1s|end=ab -n1000 http://localhost:8000/"

# Installing

Multiplex is available on PyPI at https://pypi.org/project/multiplex-sh

## Using uv (recommended)

    $ uv tool install multiplex-sh
    $ multiplex --help

## Using pip

    $ pip install multiplex-sh
    $ multiplex --help

## Direct download

Quick, from the shell:

    $ curl -o multiplex https://raw.githubusercontent.com/sebastien/multiplex/main/src/py/multiplex.py; chmod +x multiplex
    $ ./multiplex --help

# Usage

## Commands

Here are some example commands that will help understand the syntax:

Running a simple command:

    multiplex "python -m http.server"

Running a command after 5s delay:

    multiplex "+5=python -m http.server"

Running a command after another completes:

    multiplex "A=python -m http.server" "+A=ab -n1000 http://localhost:8000/"

Running multiple commands with complex coordination:

    multiplex "DB=mongod" "API+2=node server.js" "+API|end=npm test"

## Command Syntax

Commands follow a structured format: `[KEY][#COLOR][:DEP…][|ACTIONS]=COMMAND`

### Naming (`KEY=`)
- **Purpose**: Assign a name to a process for reference by other commands
- **Format**: `KEY=command` where KEY is alphanumeric (A-Z, a-z, 0-9, _)
- **Examples**: 
  - `A=python -m http.server`
  - `DB=mongod --port 27017`
  - `API_SERVER=node app.js`

### Colors (`#COLOR`)
- **Purpose**: Style channel names with colors in output
- **Named colors**: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `bright_red`, `bright_green`, etc.
- **Hex colors**: 6-digit hex codes like `FF0000` (red), `00FF00` (green), `0000FF` (blue)
- **Examples**:
  - `server#red=python -m http.server`
  - `db#blue=mongod --port 27017`
  - `worker#00FF00=python worker.py`
  - `logs#FFA500=tail -f app.log`

### Dependencies (`:DEP`)
Dependencies allow commands to wait for other processes and apply delays.

#### Dependency Format
Each dependency follows: `[KEY][&][+DELAY…]`

- **`KEY`**: Process name to wait for
- **`&`**: Optional indicator to wait for process **start** instead of **end**
- **`+DELAY`**: Optional delays to apply after the dependency condition is met

#### Dependency Types
- **End dependency**: `:A` - wait for process A to complete
- **Start dependency**: `:A&` - wait for process A to start
- **Delayed dependency**: `:A+1s` - wait for A to complete, then wait 1 second
- **Start with delay**: `:A&+500ms` - wait for A to start, then wait 500ms

#### Multiple Dependencies
- **Format**: `:DEP1:DEP2:DEP3`
- **Examples**:
  - `:A:B` - wait for both A and B to complete
  - `:A&:B+1s` - wait for A to start AND B to complete + 1s
  - `:DB:CACHE&+2s:CONFIG` - wait for DB to end, CACHE to start + 2s, and CONFIG to end

#### Delay Formats in Dependencies
- **Time unit suffixes**: `ms` (milliseconds), `s` (seconds), `m` (minutes)
- **Complex combinations**: `1m30s`, `2s500ms`, `1m1s1ms`
- **Multiple delays**: `+1s+500ms` (applies 1s delay, then 500ms delay)
- **Examples**:
  - `:A+500ms` - wait for A, then 500ms
  - `:B&+1m30s` - wait for B to start, then 90 seconds
  - `:C+1s+500ms` - wait for C, then 1s, then 500ms more

### Actions (`|ACTION`)
Actions modify process behavior:

- **`|end`**: When this process ends, terminate all other processes
- **`|silent`**: Suppress all output (stdout and stderr)
- **`|noout`**: Suppress stdout only
- **`|noerr`**: Suppress stderr only

Actions can be combined: `|silent|end=command`

### Examples by Pattern

**Sequential execution:**
```bash
multiplex "BUILD=npm run build" ":BUILD=npm start"
```

**Parallel with coordination:**
```bash
multiplex "DB=mongod" "API:DB+2s=node server.js" ":API&=npm test"
```

**Complex dependency chain:**
```bash
multiplex "CONFIG=setup" "DB:CONFIG+1s=database" "CACHE:CONFIG+500ms=redis" "API:DB:CACHE&+2s=server"
```

**Development environment:**
```bash
multiplex "DB=mongod" "API:DB+2s=npm run dev" "UI:API&+1s=npm run ui" ":UI&+5s=open http://localhost:3000"
```

### Special Cases

If your command contains an equals sign, use an empty prefix:
```bash
multiplex "=echo a=b"
```

### Global Options

**Timeout:**
- **Format**: `-t|--timeout SECONDS`
- **Purpose**: Terminate all processes after specified time
- **Example**: `multiplex -t 30 "server=python -m http.server" "test=curl localhost:8000"`

# Examples

The `examples/` directory contains practical demonstrations of multiplex features:

## Basic Patterns

**Sequential Build (`examples/sequential-build.sh`)**
```bash
multiplex "BUILD=echo 'Building...'" ":BUILD=echo 'Starting...'"
```
Demonstrates dependency-based coordination where one command waits for another to complete.

**Dependencies Demo (`examples/dependencies-demo.sh`)**
```bash
multiplex "DB=setup-database" "API:DB+1s=start-api" "UI:API&+500ms=start-ui" ":UI|end=echo 'All ready'"
```
Shows the new dependency system with end dependencies (:DB), start dependencies (:API&), and delays.

**Process Dependencies (`examples/process-delays.sh`)**  
```bash
multiplex "STEP1=echo 'init'" "STEP2:STEP1=echo 'process'" ":STEP2=echo 'done'"
```
Demonstrates chaining processes where each waits for the previous to complete.

## Real-world Scenarios

**Development environment with dependencies:**
```bash
multiplex "DB#blue=mongod" "API#green:DB+2s=node server.js" "UI#cyan:API&+500ms=npm run ui" "logs#FFA500:API&+1s=tail -f app.log"
```
Shows dependency coordination - API waits for DB to complete + 2s, UI waits for API to start + 500ms, logs wait for API to start + 1s.

**Service startup with precise timing:**
```bash
multiplex "INIT=setup" "DB#blue:INIT+1s=docker run postgres" "CACHE#yellow:INIT+500ms=redis-server" "API#green:DB:CACHE&+2s=node server.js" "HEALTH#red:API&+5s|end=curl localhost:3000/health"
```
Demonstrates complex dependencies - API waits for DB to complete AND CACHE to start, then waits 2s. Health check waits for API to start + 5s then exits.

**Color Demo (`examples/color-demo.sh`)**
```bash
multiplex "server#red=python -m http.server" "worker#00FF00=python worker.py" "monitor#cyan=system-monitor"
```
Demonstrates both named colors (red, cyan) and hex colors (00FF00 for bright green).

**Parallel Coordination (`examples/parallel-coordination.sh`)**
```bash
multiplex "DB=database" "API+2=api-server" "UI+2=ui-server" "+5=open-browser"
```
Shows how to coordinate multiple services starting in parallel with delays.

**CI/CD Pipeline (`examples/cicd-pipeline.sh`)**
```bash
multiplex "BUILD=build" "+BUILD=test" "+TESTS=deploy|end"
```
Demonstrates a realistic deployment pipeline with sequential steps.

## Advanced Features

**Actions Demo (`examples/actions-demo.sh`)**
```bash
multiplex "SERVER|silent=long-running" "+2|end=test-and-exit"
```
Shows silent processes and automatic termination with `|end` action.

**HTTP Benchmark (`examples/http-benchmark.sh`)**
```bash
multiplex "A=python -m http.server" "+A=ab -n1000 http://localhost:8000/"
```
Real HTTP server benchmarking where the test waits for server startup.

**Special Cases (`examples/special-cases.sh`)**
```bash
multiplex "=echo 'VAR=value'" "SETUP|silent=setup" "+SETUP=continue"
```
Handles commands with equals signs and complex action combinations.

**Complete Demo (`examples/complete-demo.sh`)**
```bash
multiplex "SETUP|silent=setup" "DB+1=database" "API+DB=api" "UI+API=ui" "+UI|end=done"
```
Comprehensive example showcasing all features: naming, time/process delays, actions, and coordination.

## Running Examples

All examples are executable scripts:
```bash
cd multiplex
bash examples/sequential-build.sh
bash examples/dependencies-demo.sh
bash examples/dev-environment.sh
bash examples/color-demo.sh
bash examples/time-delays.sh
bash examples/delay-suffixes-demo.sh
bash examples/http-benchmark.sh
```

Each example includes descriptive output explaining what's happening during execution.
