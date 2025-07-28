# Multiplex Examples

This directory contains practical examples demonstrating multiplex features and common usage patterns.

## Basic Patterns
- **`sequential-build.sh`** - Process waits for another to complete (`A=build` then `+A=start`)
- **`time-delays.sh`** - Time-based delays (`+1`, `+2.5`, etc.)
- **`process-delays.sh`** - Chain of dependent processes (`STEP1` → `+STEP1` → `+STEP2`)

## Real-world Scenarios
- **`dev-environment.sh`** - Full development stack startup (DB → API → UI → Browser)
- **`parallel-coordination.sh`** - Multiple services with coordinated timing
- **`cicd-pipeline.sh`** - CI/CD pipeline simulation (build → test → deploy)
- **`http-benchmark.sh`** - HTTP server benchmarking with Apache Bench

## Advanced Features
- **`actions-demo.sh`** - Silent processes and auto-termination (`|silent`, `|end`)
- **`special-cases.sh`** - Commands with equals signs and complex patterns
- **`complete-demo.sh`** - Comprehensive demonstration of all features

## Running Examples

Make sure you're in the multiplex directory and have the Python path set:

```bash
cd multiplex
PYTHONPATH=src/py bash examples/sequential-build.sh
PYTHONPATH=src/py bash examples/dev-environment.sh
PYTHONPATH=src/py bash examples/complete-demo.sh
```

Or run them directly with the Python module:

```bash
python3 -m multiplex "A=echo starting" "+A=echo finished"
```

Each example includes descriptive output explaining what's happening during execution.