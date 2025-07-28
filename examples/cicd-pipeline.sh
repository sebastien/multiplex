#!/usr/bin/env bash
# Complex coordination example: realistic CI/CD pipeline simulation
PYTHON="${PYTHON:-python3}"
echo "Running complex coordination example..."
echo "Simulating CI/CD pipeline: build -> test -> deploy"
$PYTHON -m multiplex \
    "BUILD=echo 'Building application...'; sleep 2; echo 'Build completed successfully'" \
    "DEPS+1=echo 'Installing dependencies...'; sleep 1; echo 'Dependencies installed'" \
    "+BUILD=echo 'Running unit tests...'; sleep 1; echo 'Unit tests passed'" \
    "+TESTS=echo 'Running integration tests...'; sleep 1; echo 'Integration tests passed'" \
    "+INTEGRATION|end=echo 'Deploying to production...'; sleep 1; echo 'Deployment successful!'"