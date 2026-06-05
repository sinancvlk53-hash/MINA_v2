#!/bin/bash
journalctl -u mina-engine.service --since '2026-06-05 19:13:00' --until '2026-06-05 19:15:00' -n 500 2>&1 | cat
