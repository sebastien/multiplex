#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import cli


def test_cli_ctrl_c():
	"""Test CLI with Ctrl-C handling"""
	print("Testing CLI with long-running command...")
	print("This will start a sleep command - press Ctrl-C to test termination")

	# Simulate CLI args for a long-running command
	cli(["sleep 30"])


if __name__ == "__main__":
	test_cli_ctrl_c()
