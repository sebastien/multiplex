#!/usr/bin/env bash
# Delay suffixes demo: showcasing new millisecond, second, minute, and combined timing features
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===== Delay Suffixes Demo ====="
echo "This example demonstrates the new delay suffix functionality:"
echo "- ms: milliseconds"
echo "- s: seconds" 
echo "- m: minutes"
echo "- Complex combinations: 1m30s750ms, 2s500ms, etc."
echo ""
echo "Timeline:"
echo "  0ms       - Starting services..."
echo "  100ms     - Quick response"
echo "  2s        - After 2 seconds"
echo "  1m        - One minute later"
echo "  1m30s750ms - Complex timing (90.75 seconds)"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "echo 'Starting services...'" \
    "+100ms=echo 'Quick response (100ms)'" \
    "+2s=echo 'After 2 seconds'" \
    "+1m=echo 'One minute later'" \
    "+1m30s750ms=echo 'Complex timing - 90.75 seconds'"

echo ""
echo "===== Advanced Service Coordination ====="
echo "Real-world example showing complex delay combinations:"
echo ""

$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "DB#blue=echo 'Database: Starting PostgreSQL...'" \
    "CACHE#yellow+250ms=echo 'Cache: Redis starting (quick init)...'" \
    "API#green+2s500ms=echo 'API: Starting Node.js server (precise timing)...'" \
    "UI#cyan+3s=echo 'UI: Starting React dev server...'" \
    "MONITOR#magenta+1m=echo 'Monitor: Starting system monitoring...'" \
    "HEALTH#red+1m5s500ms|end=echo 'Health check: All services ready after 65.5s!'"