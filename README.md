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
one-liner:

    multiplex "|silent=python -m http.server" "+1|end=ab -n1000 http://localhost:8000/"

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

Commands follow a structured format: `[KEY][#COLOR][+DELAY][|ACTIONS]=COMMAND`

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

### Delays (`+DELAY`)
Commands can be delayed in two ways:

#### Time-based delays
- **Format**: `+SECONDS` where SECONDS can be integer or decimal
- **Examples**:
  - `+5=python script.py` (wait 5 seconds)
  - `+1.5=echo "delayed"` (wait 1.5 seconds)
  - `SERVER+10=curl localhost:8000` (named SERVER, wait 10s)

#### Process-based delays  
- **Format**: `+PROCESS_NAME` wait for named process to complete
- **Examples**:
  - `+A=ab -n1000 http://localhost:8000/` (wait for process A)
  - `+DB=node migrate.js` (wait for DB process to complete)
  - `+SERVER=echo "server is done"` (wait for SERVER process)

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
multiplex "BUILD=npm run build" "+BUILD=npm start"
```

**Parallel with coordination:**
```bash
multiplex "DB=mongod" "API+2=node server.js" "+API=npm test"
```

**Benchmark pattern:**
```bash
multiplex "SERVER|silent=python -m http.server" "+1|end=ab -n1000 http://localhost:8000/"
```

**Development environment:**
```bash
multiplex "DB=mongod" "API+2=npm run dev" "UI+2=npm run ui" "+5=open http://localhost:3000"
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
multiplex "BUILD=echo 'Building...'" "+BUILD=echo 'Starting...'"
```
Demonstrates process-based delays where one command waits for another to complete.

**Time-based Delays (`examples/time-delays.sh`)**
```bash
multiplex "echo 'immediate'" "+1=echo 'after 1s'" "+2.5=echo 'after 2.5s'"
```
Shows different timing patterns with integer and decimal delays.

**Process Dependencies (`examples/process-delays.sh`)**
```bash
multiplex "STEP1=echo 'init'" "STEP2+STEP1=echo 'process'" "+STEP2=echo 'done'"
```
Demonstrates chaining processes where each waits for the previous to complete.

## Real-world Scenarios

**Development environment with colors:**
```bash
multiplex "DB#blue=mongod" "API#green+2=node server.js" "UI#cyan+2=npm run ui" "logs#FFA500+5=tail -f app.log"
```
Shows how to use colors to visually distinguish different services in a development stack.

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
bash examples/dev-environment.sh
bash examples/color-demo.sh
bash examples/http-benchmark.sh
```

Each example includes descriptive output explaining what's happening during execution.
