#!/bin/bash

# Timestamp demonstration script
# Shows how to use the --timestamp and -r/--relative options

echo "=== Multiplex Timestamp Feature Demo ==="
echo

echo "1. Basic timestamp usage (--timestamp):"
echo "   Shows absolute timestamps in HH:MM:SS format"
echo
echo "   Command: multiplex --timestamp 'A=echo hello from A' 'B+1s=cat'"
echo
multiplex --timestamp 'A=echo hello from A' 'B+1s=cat' <<< "hello from A"
echo

echo "2. Relative timestamp usage (--timestamp -r):"
echo "   Shows timestamps relative to start time (00:00:00)"
echo
echo "   Command: multiplex --timestamp -r 'A=echo hello from A' 'B+1s=cat'"
echo
multiplex --timestamp -r 'A=echo hello from A' 'B+1s=cat' <<< "hello from A"
echo

echo "3. More complex example with multiple processes and delays:"
echo "   Demonstrates timestamps with process coordination"
echo
echo "   Command: multiplex --timestamp -r 'server+2s=echo Server starting...' 'client:server&+500ms=echo Client connecting...'"
echo
multiplex --timestamp -r 'server+2s=echo Server starting...' 'client:server&+500ms=echo Client connecting...'
echo

echo "4. Comparing with and without timestamps:"
echo
echo "   Without timestamps:"
multiplex 'A=echo hello' 'B+500ms=echo world'
echo
echo "   With relative timestamps:"
multiplex --timestamp -r 'A=echo hello' 'B+500ms=echo world'
echo

echo "=== Demo Complete ==="