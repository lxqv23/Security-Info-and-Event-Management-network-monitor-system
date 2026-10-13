import win32com.client
import pythoncom
import zmq
import json
import errno
import sys
import threading
import shutil
import subprocess

port = 48268

# Set broadcast to main function
try:
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.connect(f"tcp://127.0.0.1:{port}")

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

class firewalls():
    def __init__(self, action:list = ["view"]):
        self.action = action
        self.stream_firewalls()
    def stream_firewalls(self):
        threads = []
        if ("view" in self.action):
            t1 = threading.Thread(target=self.view_firewall_rules, daemon=True)
            t1.start()
            threads.append(t1)
        if ("edit" in self.action):
            t2 = threading.Thread(target=self.edit_firewall_rules, daemon=True)
            t2.start()
            threads.append(t2)

        # Keep the main thread alive so background threads can work
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\nShutting down firewall streams...")
        finally:
            socket.close()
            context.term()
    def linux_get_installed_firewall(self):
        tools = ['firewall-cmd', 'ufw', 'nft', 'iptables']
        for tool in tools:
            if shutil.which(tool) is not None:
                return tool
        return None
    def view_firewall_rules(self):
        # Windows 
        if sys.platform == "win32":
            pythoncom.CoInitialize()
            try:
                firewall_policy = win32com.client.Dispatch("HNetCfg.FwPolicy2")
                firewall_rules = firewall_policy.Rules

                for rule in firewall_rules:
                    if rule.Enabled:
                        payload = {
                        "Name": str(rule.Name),
                        "Description": str(rule.Description),
                        "Protocol": str(rule.Protocol),
                        "Local_ports": str(rule.LocalPorts),
                        "Action": str('Allow' if rule.Action == 1 else 'Block'),
                        "Direction": str('Inbound' if rule.Direction == 1 else 'Outbound')
                    }
                    # Send out via socket if it was passed in
                    json_data = json.dumps(payload)
                    socket.send_string(json_data)
            except Exception as e:
                print(f"An error occurred accessing the COM interface: {e}")
            finally:
                pythoncom.CoUninitialize()
        elif sys.platform.startswith("linux"):
            tool = self.linux_get_installed_firewall()
            if not tool:
                print("Error: No recognixed firewall utility on the Linux system")
                return
            commands = {
            'firewall-cmd': ['sudo', 'firewall-cmd', '--list-all'],
            'ufw':          ['sudo', 'ufw', 'status', 'verbose'],
            'nft':          ['sudo', 'nft', 'list', 'ruleset'],
            'iptables':     ['sudo', 'iptables', '-S']
            }
            cmd = commands[tool]
            try:
                rules = subprocess.run(cmd, capture_output=True, text=True, check=True)
                print(result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"Firewall Execution failed. Ensure script is run with 'sudo'.\nError: {e.stderr}", file=sys.stderr)
            except PermissionError:
                print("Firewall Permission Denied: This script requires root (sudo) privileges.", file=sys.stderr)

    def edit_firewall_rules(self):
        pass