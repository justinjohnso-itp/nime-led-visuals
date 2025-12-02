#!/bin/bash
cd "$(dirname "$0")/../.."
sudo "$(which python)" scripts/tests/test_led.py
