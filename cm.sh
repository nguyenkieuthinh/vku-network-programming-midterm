# Run Step 1 (Sequential blocking demo)
python3 01_single_client_echo.py

# Run Step 2 (Concurrent echo)
python3 02_multiclient_spawn.py

# Run Step 3 (Shared-lock case study)
python3 03_arc_mutex_pitfall.py

# Run Step 4 (Full Broadcast Chat Server)
python3 04_broadcast_chat.py


# client connect:
nc 127.0.0.1 8080
