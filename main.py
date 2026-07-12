import os
import ctypes
import sys
import logs
import zmq
import json
import errno
import threading

port = 48268

# Recieve data from applications
try:
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://127.0.0.1:{port}")

except zmq.error.ContextTerminated:
    print("Error: The ZeroMQ context was terminated.")
except zmq.ZMQError as e:
    if e.errno == errno.EADDRINUSE:
        print(f"Error: Port {port} is already in use by another process")
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
    #start streaming logs
    log_stream = threading.Thread(target=logs.stream_logs, daemon=True)
    log_stream.start()
    try:
        while True:
            try:

                message = socket.recv_string()
                log_data = json.loads(message)
                print(log_data)

            except KeyboardInterrupt:
                break
    finally:
        socket.close()
        context.term()

    
if __name__ == "__main__":
    main()