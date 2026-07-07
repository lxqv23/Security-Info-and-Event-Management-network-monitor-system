import docker
import zmq
import json
import errno
import subprocess
import win32evtlog
import threading


# Set broadcast to main function
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

class stream_logs():
    def __init__(self, applications:list = ["docker", "system"]):
        self.applications = applications
        self.start_logs()

    def start_logs(self):
        if  "docker" in self.applications:
            threading.Thread(target=self.docker_logs,args=()).start()
        if  "system" in self.applications:
            threading.Thread(target=self.system_logs, args=()).start()

    def docker_logs(self):
        # Connect to defualt docker socket
        try:
            client = docker.from_env()
        except Exception as e:
            print(f"Docker Error: Possibly not installed : {e}")
            return 1
        
        #stream docker logs to main
        try:
            for docker_log in client.logs(stream=True):
                socket.send_string(json.dumps(docker_log.strip))
        except docker.errors.APIError as e:
            print(f"Error: Docker server error {e}")
            return 1
        
    def system_logs(self):
        # Linux

        # start streaming all system logs
        try:
            logs = subprocess.Popen(["sudo", "journalctl", "-f"], stdout=subprocess.PIPE, text=True)
        except subprocess.SubprocessError as e:
            print(f"Error: {e}")
        
        # stream system logs to main
        try:
            for sys_logs in logs.stdout:
                socket.send_string(json.dumps(sys_logs.strip))
        except Exception as e:
            print(f"Error: {e}")
        
        # Windows 

        # Select the type of windws log
        log_channel = "Security"
        
        try:
            hand = win32evtlog.OpenEventLog(None, log_channel)
            flags = win32evtlog.EVENTLOG_SEQUENTIAL_READ | win32evtlog.EVENTLOG_BACKWARDS_READ
        except Exception as e:
            print(f"Error: {e}")
        
        try:
            for sys_logs in win32evtlog.ReadEventLog(hand, flags, 0):
                event_id = sys_logs.EventID & 0xFFFF
                socket.send_string(json.dumps(f"[{sys_logs.TimeGenerated}] Event ID: {event_id}"))
        except Exception as e:
            print(f"Error: {e}")
