#!/bin/bash
sed -i '' '/environment:/i \
    volumes:\
      - ./backend/app/services/openclaw/gateway_rpc.py:/app/app/services/openclaw/gateway_rpc.py\
' compose.yml
