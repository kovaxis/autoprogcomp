#!/usr/bin/env python3

import sys

txt = sys.stdin.read()
lines = txt.splitlines()
teams: list[list[str]] = [[]]
for rawline in lines:
    line = rawline.strip()
    if ":" in line:
        line = ""
    elif " " in line:
        line = line.split()[-1]
    if not line and teams[-1]:
        teams.append([])
    if line:
        teams[-1].append(line)

if not teams[-1]:
    teams.pop()

sys.stdout.write("[")
for i, team in enumerate(teams):
    if i > 0:
        sys.stdout.write(",")
    sys.stdout.write("[")
    for j, member in enumerate(team):
        if j > 0:
            sys.stdout.write(",")
        sys.stdout.write("'")
        sys.stdout.write(member)
        sys.stdout.write("'")
    sys.stdout.write("]")
sys.stdout.write("]\n")
