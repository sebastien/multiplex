#!/usr/bin/env bash
# Dependencies demo: showcasing the new upgraded command format with dependencies
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===== Dependencies Demo ====="
echo "This example demonstrates the new upgraded command format:"
echo ""
echo "Format: [KEY][#COLOR][:DEP…][|ACTION…]=COMMAND"
echo "Where DEP is: [KEY][&][+DELAY…]"
echo ""
echo "Features demonstrated:"
echo "- Basic dependencies: :A (wait for A to end)"
echo "- Start dependencies: :A& (wait for A to start)"
echo "- Delayed dependencies: :A+1s (wait for A to end, then 1s)"
echo "- Multiple dependencies: :A:B+500ms"
echo "- Complex combinations with colors and actions"
echo ""

echo "=== Example 1: Simple Sequential Dependencies ==="
echo "DB -> API -> UI chain"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "DB#blue=sleep 2 && echo 'Database: Ready'" \
    "API#green:DB=sleep 1 && echo 'API: Connected to DB, ready'" \
    "UI#cyan:API=echo 'UI: Connected to API, ready'" \
    ":UI=echo 'All services ready!'"

echo ""
echo "=== Example 2: Dependencies with Delays ==="
echo "Services with startup delays and coordination"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "SETUP#yellow=sleep 1 && echo 'Setup: Configuration complete'" \
    "DB#blue:SETUP+500ms=sleep 2 && echo 'Database: Started after setup + 500ms'" \
    "CACHE#magenta:SETUP+1s=sleep 1 && echo 'Cache: Started after setup + 1s'" \
    "API#green:DB:CACHE+2s=echo 'API: Started after DB and Cache + 2s'" \
    ":API|end=echo 'System fully operational'"

echo ""
echo "=== Example 3: Start Dependencies with & ==="
echo "Waiting for process start rather than completion"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "SERVER#red=sleep 5 && echo 'Server: Long running process finished'" \
    "MONITOR#cyan:SERVER&+100ms=echo 'Monitor: Started monitoring SERVER after it began + 100ms'" \
    "HEALTH#yellow:SERVER&+1s=echo 'Health check: Started checking SERVER after it began + 1s'" \
    ":SERVER|end=echo 'Server process completed'"

echo ""
echo "=== Example 4: Complex Multiple Dependencies ==="
echo "Complex dependency graph with mixed start/end dependencies"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "INIT#gray=sleep 1 && echo 'Init: System initialization'" \
    "DB#blue:INIT=sleep 2 && echo 'Database: Online'" \
    "QUEUE#orange:INIT+500ms=sleep 1 && echo 'Queue: Online'" \
    "API#green:DB:QUEUE&+1s=sleep 1 && echo 'API: Started after DB done and Queue started + 1s'" \
    "WORKER#purple:API&:QUEUE+2s=echo 'Worker: Started after API starts and Queue done + 2s'" \
    "MONITOR#cyan:API&:DB&:QUEUE&+500ms=echo 'Monitor: Watching all services after they start + 500ms'" \
    ":API:WORKER|end=echo 'Core services ready, system operational'"

echo ""
echo "=== Example 5: Development Environment Setup ==="
echo "Realistic development environment with proper dependency management"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "CONFIG#gray|silent=echo 'Loading configuration...' && sleep 1" \
    "DB#blue:CONFIG+100ms=echo 'PostgreSQL: Starting database...' && sleep 3 && echo 'PostgreSQL: Ready on port 5432'" \
    "REDIS#red:CONFIG+200ms=echo 'Redis: Starting cache...' && sleep 1 && echo 'Redis: Ready on port 6379'" \
    "MIGRATE#yellow:DB+500ms|silent=echo 'Running database migrations...' && sleep 2" \
    "API#green:MIGRATE:REDIS+1s=echo 'API Server: Starting on port 3000...' && sleep 2 && echo 'API Server: Ready'" \
    "FRONTEND#cyan:API&+500ms=echo 'Frontend: Starting development server...' && sleep 2 && echo 'Frontend: Ready on port 8080'" \
    "TESTS#magenta:API+2s|end=echo 'Running integration tests...' && sleep 3 && echo 'All tests passed!'"

echo ""
echo "===== Dependencies Demo Complete ====="