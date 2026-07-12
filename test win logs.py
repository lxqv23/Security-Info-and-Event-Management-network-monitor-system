import time
import win32evtlog
import win32event
import xml.etree.ElementTree as ET


def event_callback(action, context, event_handle):
    if action == win32evtlog.EvtSubscribeActionDeliver:
        try:
            # 1. Get raw XML from Windows
            xml_content = win32evtlog.EvtRender(event_handle, win32evtlog.EvtRenderEventXml)
            root = ET.fromstring(xml_content)
            
            # 2. Extract Event ID safely using a namespace-agnostic wildcard search
            event_id_elem = root.find('.//{*}EventID')
            event_id = event_id_elem.text if event_id_elem is not None else "Unknown ID"
            
            # 3. Extract TimeCreated safely
            time_elem = root.find('.//{*}TimeCreated')
            time_created = time_elem.get('SystemTime') if time_elem is not None else "Unknown Time"
            
            # 4. Extract Target User safely
            user_name = "N/A"
            data_elems = root.findall('.//{*}Data')
            for data in data_elems:
                name_attr = data.get('Name')
                if name_attr in ['TargetUserName', 'SubjectUserName']:
                    user_name = data.text if data.text is not None else "N/A"
                    break

            print(f"[{time_created}] Event ID: {event_id} | User: {user_name}")
            
        except Exception as e:
            print(f"Error parsing event: {e}")
            
    return 0


def stream_security_logs():
    print("Initializing Security Log Stream... Press Ctrl+C to exit.")
    
    try:
        # Subscribe to the Security log channel
        # Use "*" query to get all events, or "Event/System[EventID=4624]" for logins only
        subscription = win32evtlog.EvtSubscribe("Security", win32evtlog.EvtSubscribeToFutureEvents, None, event_callback, None, "*", None, None)
    except Exception as e:
        print(f"Subscription failed: {e}")
        print("Ensure you are running this script with Administrator/Elevated privileges.")
        return

    # Keep the main thread running to listen for events
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping log stream.")

if __name__ == "__main__":
    stream_security_logs()
