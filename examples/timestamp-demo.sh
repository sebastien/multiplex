#!/bin/bash

# Timestamp demonstration script
# Shows how to use the --time and --time-relative options

echo "=== Multiplex Timestamp Feature Demo ==="
echo

echo "1. Basic timestamp usage (--time):"
echo "   Shows absolute timestamps in HH:MM:SS format"
echo
echo "   Command: multiplex --time 'A=echo hello from A' 'B+1s=cat'"
echo
multiplex --time 'A=echo hello from A' 'B+1s=cat' <<< "hello from A"
echo

echo "2. Relative timestamp usage (--time=relative):"
echo "   Shows timestamps relative to start time (00:00:00)"
echo
echo "   Command: multiplex --time=relative 'A=echo hello from A' 'B+1s=cat'"
echo
multiplex --time=relative 'A=echo hello from A' 'B+1s=cat' <<< "hello from A"
echo

echo "3. More complex example with multiple processes and delays:"
echo "   Demonstrates timestamps with process coordination"
echo
echo "   Command: multiplex --time=relative 'server+2s=echo Server starting...' 'client:server&+500ms=echo Client connecting...'"
echo
multiplex --time=relative 'server+2s=echo Server starting...' 'client:server&+500ms=echo Client connecting...'
echo

echo "4. Comparing with and without timestamps:"
echo
echo "   Without timestamps:"
multiplex 'A=echo hello' 'B+500ms=echo world'
echo
echo "   With relative timestamps:"
multiplex --time=relative 'A=echo hello' 'B+500ms=echo world'
echo

echo "=== Demo Complete ==="