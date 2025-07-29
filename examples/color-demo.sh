#!/bin/bash

# Multiplex Color Demo
# This script demonstrates the new color functionality in multiplex

echo "=== Multiplex Color Demo ==="
echo "This demonstrates how to use colors in multiplex channel names"
echo ""

echo "Running multiplex with colored channels..."
echo ""

# Run multiplex with different color styles
python3 -m multiplex \
  "server#red=echo 'Starting web server...'; sleep 2; echo 'Server running on port 8080'" \
  "db#blue=echo 'Initializing database...'; sleep 1.5; echo 'Database ready'" \
  "worker#green=echo 'Starting background worker...'; sleep 1; echo 'Worker processing jobs'" \
  "monitor#00FF00=echo 'System monitor active'; sleep 0.5; echo 'CPU: 15% Memory: 45%'" \
  "logs#FFA500=echo 'Log aggregator starting'; sleep 1; echo 'Collecting logs from all services'" \
  "cache#cyan=echo 'Redis cache warming up'; sleep 0.8; echo 'Cache ready for connections'"

echo ""
echo "=== Color Examples ==="
echo "Named colors used: red, blue, green, cyan"
echo "Hex colors used: 00FF00 (bright green), FFA500 (orange)"
echo ""
echo "Available named colors:"
echo "  Basic: black, red, green, yellow, blue, magenta, cyan, white" 
echo "  Bright: bright_black, bright_red, bright_green, bright_yellow,"
echo "          bright_blue, bright_magenta, bright_cyan, bright_white"
echo ""
echo "Hex colors: Use 6-digit hex codes like FF0000 (red), 00FF00 (green), 0000FF (blue)"