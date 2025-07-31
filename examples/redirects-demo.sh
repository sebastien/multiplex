#!/bin/bash

# Redirect Demo - Demonstrates stdin redirection from process outputs
#
# This demonstrates the new redirect functionality:
# - `<A…` map stdin to `A` stdout
# - `<2A…` map stdin to `A` stderr
# - `<(1A,2A)…` map stdin to `A`'s stdout and stderr combined
# - `<(A,B)…` map stdin to `A`'s stdout and `B`s stdout

echo "=== Redirect Demo ==="
echo ""

echo "1. Simple stdout redirect: A produces output, B consumes it via stdin"
echo "Command: multiplex --timeout 1 'A=echo \"Hello from A\"' '<A=cat'"
python3 ../src/py/multiplex.py --timeout 1 'A=echo "Hello from A"' '<A=cat'
echo ""

echo "2. Stderr redirect: A produces stderr, B consumes it via stdin"
echo "Command: multiplex --timeout 1 'A=python3 -c \"import sys; sys.stderr.write(\\\"Error from A\\\\n\\\")\"' '<2A=cat'"
python3 ../src/py/multiplex.py --timeout 1 'A=python3 -c "import sys; sys.stderr.write(\"Error from A\\n\")"' '<2A=cat'
echo ""

echo "3. Combined stdout and stderr redirect: A produces both, B consumes both via stdin"
echo "Command: multiplex --timeout 1 'A=python3 -c \"print(\\\"stdout\\\"); import sys; sys.stderr.write(\\\"stderr\\\\n\\\")\"' '<(1A,2A)=cat'"
python3 ../src/py/multiplex.py --timeout 1 'A=python3 -c "print(\"stdout\"); import sys; sys.stderr.write(\"stderr\\n\")"' '<(1A,2A)=cat'
echo ""

echo "4. Multiple processes redirect: Both A and B produce output, C consumes both via stdin"
echo "Command: multiplex --timeout 1 'A=echo \"from A\"' 'B=echo \"from B\"' '<(A,B)=cat'"
python3 ../src/py/multiplex.py --timeout 1 'A=echo "from A"' 'B=echo "from B"' '<(A,B)=cat'
echo ""

echo "5. Complex example with dependencies: A starts, B waits for A to start, C processes both outputs"
echo "Command: multiplex --timeout 1 'A=echo \"Starting process A\"' 'B:A&=echo \"B started after A\"' '<(A,B)=sort'"
python3 ../src/py/multiplex.py --timeout 1 'A=echo "Starting process A"' 'B:A&=echo "B started after A"' '<(A,B)=sort'
echo ""

echo "6. Full format with redirect: Named processes with colors, dependencies, redirects, and actions"
echo "Command: multiplex --timeout 1 'producer#green=echo \"data\"' 'processor#blue<producer:producer|silent=wc -c'"
python3 ../src/py/multiplex.py --timeout 1 'producer#green=echo "data"' 'processor#blue<producer:producer|silent=wc -c'
echo ""

echo "✅ Redirect demo completed!"