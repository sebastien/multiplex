#!/usr/bin/env bash
# Process-based delays example: sequential process dependencies
PYTHON="${PYTHON:-python3}"
echo "Running process-based delays example..."
echo "Each process waits for the previous one to complete"
$PYTHON -m multiplex \
    "STEP1=echo 'Step 1: Initializing...'; sleep 1; echo 'Step 1 complete'" \
    "STEP2+STEP1=echo 'Step 2: Processing...'; sleep 1; echo 'Step 2 complete'" \
    "STEP3+STEP2=echo 'Step 3: Finalizing...'; sleep 1; echo 'Step 3 complete'" \
    "+STEP3=echo 'All steps completed successfully!'"