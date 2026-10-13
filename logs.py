import docker.errors
import docker
import zmq
import json
import errno
import subprocess
import win32evtlog
import win32event
import threading
import sys
import time
import xml.etree.ElementTree as ET

port = 48268

# Set broadcast to main function
try:
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://127.0.0.1:{port}")

except zmq.error.ContextTerminated:
    print("Logs Error: The ZeroMQ context was terminated.")
except zmq.ZMQError as e:
    if e.errno == errno.EADDRINUSE:
        print(f"Logs Error: Port {port} is already in use by another process")
    elif e.errno == errno.EINVAL:
        print("Logs Error: Invaild endpoint supplied")
    elif e.errno == errno.EADDRNOTAVAIL:
        print("Logs Error: The provided address was not locally avaible")
    elif e.errno == errno.ENOTSOCK:
        print("Logs Error: The socket was invalid")
    else:
        print(f"ZeroMQ Logs Error: ({e.errno}): {e}")
except Exception as e:
    print(f"An unexpected Logs non-ZMQ error occurred: {e}")

def win_logs_callback(action, context, event_handle):
    if action == win32evtlog.EvtSubscribeActionDeliver:
        try:
            # 1. Get raw XML from Windows
            xml_content = win32evtlog.EvtRender(event_handle, win32evtlog.EvtRenderEventXml)
            root = ET.fromstring(xml_content)
            
            # 2. Extract Event ID
            event_id_elem = root.find('.//{*}EventID')
            event_id = event_id_elem.text if event_id_elem is not None else "Unknown ID"
            
            # 3. Extract TimeCreated
            time_elem = root.find('.//{*}TimeCreated')
            time_created = time_elem.get('SystemTime') if time_elem is not None else "Unknown Time"
            
            # 4. Extract Target User
            user_name = "N/A"
            data_elems = root.findall('.//{*}Data')
            source_computer = "Local/Unknown"
            for data in data_elems:
                data_name = data.get('Name')
                if data_name in ['TargetUserName', 'SubjectUserName']:
                    user_name = data.text if data.text is not None else "N/A"
                # Extract remote source workstation name or IP
                elif data_name in ['WorkstationName', 'IpAddress']:
                    # Only overwrite if we find a valid string value
                    if data.text and data.text.strip() and data.text != "-":
                        source_computer = data.text.strip()

            payload = {
                "timestamp": str(time_created),
                "event_id": event_id,
                "User": str(user_name),
                "Source_computer": str(source_computer)
            }
            # Send out via your socket if it was passed in
            json_data = json.dumps(payload)
            if socket:
                socket.send_string(json_data)
            else:
                # Fallback print for debugging if socket isn't connected
                print(f"[STREAM] {json_data}")
            
        except Exception as e:
            print(f"Error parsing event: {e}")
            
    return 0

class stream_logs():
    def __init__(self, applications:list = ["docker", "system"]):
        self.applications = applications
        self.start_logs()

    def start_logs(self):
        threads = []
        if "docker" in self.applications:
            t1 = threading.Thread(target=self.docker_logs, daemon=True)
            t1.start()
            threads.append(t1)
        if "system" in self.applications:
            t2 = threading.Thread(target=self.system_logs, daemon=True)
            t2.start()
            threads.append(t2)
        
        # Keep the main thread alive so background threads can work
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\nShutting down log streams...")
        finally:
            socket.close()
            context.term()

    def docker_logs(self):
        # Connect to defualt docker socket
        try:
            client = docker.from_env()
            #stream docker logs to main
            for event in client.events(decode=True):
                msg = f"[Docker] {event.get('Type')} - {event.get('Action')} ({event.get('Actor', {}).get('Attributes', {}).get('name', '')})"
                socket.send_string(json.dumps(msg))
        except docker.errors.APIError as e:
            print(f"Logs Error: Docker server error {e}")
            return 1
        except Exception as e:
            print(f"Logs Docker Error: Possibly not installed : {e}")
            return 1
        
    def system_logs(self):
        # Linux
        if sys.platform.startswith("linux"):
            # start streaming all system logs
            try:
                logs = subprocess.Popen(["sudo", "journalctl", "-f"], stdout=subprocess.PIPE,stderr=subprocess.STDOUT, text=True,bufsize=1)
            except subprocess.SubprocessError as e:
                print(f"Error: {e}")
            
            # stream system logs to main
            try:
                for sys_logs in iter(logs.stdout.readline, ""):
                    cleaned_log = sys_logs.strip()
                    if cleaned_log:  # Skip empty lines
                        socket.send_string(json.dumps(cleaned_log))
            except Exception as e:
                print(f"Logs Error: {e}")
            finally:
                if logs.poll() is None:
                    logs.terminate()
                    logs.wait()
        
        # Windows 
        elif sys.platform == "win32":
            NS = {'ns': 'http://microsoft.com'}

            # Select the type of windws log
            log_channel = "Security"
            try:
                subscription = win32evtlog.EvtSubscribe(log_channel, win32evtlog.EvtSubscribeToFutureEvents, None, win_logs_callback, None, "*", None, None)
            except Exception as e:
                print(f"Subscription failed: {e}")
                print("CRITICAL: Verify this is running via CMD/IDE as an ADMINISTRATOR.")
                return
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping log stream.")