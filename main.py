import os
import ctypes
import sys
import logs
import zmq
import json
import errno

# Recieve data from applications
try:
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://127.0.0.1:7268")

except zmq.error.ContextTerminated:
    print("Error: The ZeroMQ context was terminated.")
except zmq.ZMQError as e:
    if e.errno == errno.EADDRINUSE:
        print("Error: Port 7268 is already in use by another process")
    elif e.errno == errno.EINVAL:
        print("Error: Invaild endpoint supplied")
    elif e.errno == errno.EADDRNOTAVAIL:
        print("Error: The provided address was not locally avaible")
    elif e.errno == errno.ENOTSOCK:
        print("Error: The socket was invalid")
    else:
        print(f"ZeroMQ Error: ({e.errno}): {e}")
except Exception as e:
    print(f"An unexpected non-ZMQ error occurred: {e}")

socket.setsockopt_string(zmq.SUBSCRIBE, "")


def is_admin():
    try:
        return os.getuid() == 0
    except AttributeError:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError:
            return False
if not(is_admin()):
    print("Error: Privs not admin")
    sys.exit()

def main():
    while True:
        #start streaming logs
        logs.stream_logs

        message = socket.recv_string()
        log_data = json.loads(message)
        print(log_data)
    
if __name__ == "__main__":
    main()