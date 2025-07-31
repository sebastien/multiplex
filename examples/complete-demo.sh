#!/usr/bin/env bash
# Complete feature demonstration: all multiplex capabilities in one example
PYTHON="${PYTHON:-python3}"
echo "Running complete feature demonstration..."
echo "This example showcases: naming, time delays, process delays, actions, and coordination"
echo ""
$PYTHON -m multiplex \
    "SETUP|silent=echo 'Silent setup process...'; sleep 1" \
    "+0.5=echo 'Immediate startup message'" \
    "DB+1=echo 'Database starting...'; sleep 2; echo 'Database ready on port 5432'" \
    "CACHE+1.5=echo 'Cache starting...'; sleep 1; echo 'Redis ready on port 6379'" \
    "API:DB=echo 'API waiting for database...'; sleep 1; echo 'API ready on port 8000'" \
    "UI:API=echo 'UI waiting for API...'; sleep 1; echo 'React UI ready on port 3000'" \
    "HEALTH+2=echo 'Health check starting...'; sleep 1; echo 'All services healthy'" \
    ":HEALTH|end=echo 'System ready! Shutting down demo...'"
echo ""
echo "✓ Complete demonstration finished"