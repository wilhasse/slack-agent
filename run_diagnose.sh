#!/bin/bash
cd /home/cslog/svn/ticslog_trunk/python/slack_agent
source venv/bin/activate
python diagnose.py "$@"
