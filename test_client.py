import requests
import json
import uuid
import sys

BASE_URL = "http://localhost:8080/"

def send_message(session_id, text):
    """Sends a message to the agent and prints the JSON response."""
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": session_id,
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"text": text}]
            }
        }
    }
    
    print(f"\n--- Sending to Session: {session_id} ---")
    print(f"User: {text}")
    
    try:
        response = requests.post(BASE_URL, json=payload)
        response.raise_for_status()
        
        # Pretty print the JSON output
        print("\nAgent Response:")
        print(json.dumps(response.json(), indent=2))
        
        # Check if the agent is asking a question
        res_data = response.json()
        if "result" in res_data and "parts" in res_data["result"]:
            for part in res_data["result"]["parts"]:
                if "text" in part:
                    print(f"\n[!] AGENT SAYS: {part['text']}")
                    
    except Exception as e:
        print(f"Error connecting to agent: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_client.py [1, 2, or 3]")
        sys.exit(1)

    case = sys.argv[1]

    if case == "1":
        # Case 1: The One-Shot Success
        send_message("case-1-oneshot", "Fetch sales from v2_api, clean it, and make a bar chart.")

    elif case == "2":
        # Case 2: Resiliency (The 429 Retry)
        send_message("case-2-retry", "Run the standard pipeline from v2_api and make a pie chart.")

    elif case == "3":
        # Case 3: The HITL (The 3D-Holographic failure)
        # Run this twice: First to trigger the fail, then to rescue.
        print("Note: Run this once to fail, then edit the script to send a 'rescue' message.")
        send_message("case-3-hitl", "Fetch data and generate a 3D-Holographic chart.")

    else:
        # Custom input
        custom_text = " ".join(sys.argv[1:])
        send_message("custom-session", custom_text)