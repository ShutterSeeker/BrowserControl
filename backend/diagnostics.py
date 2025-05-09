import requests

SERVER_IP = "10.110.7.120"
PORT = 5000
ENDPOINT = "/lookup_lp_by_gtin"

url = f"http://{SERVER_IP}:{PORT}{ENDPOINT}"

print(f"Testing connection to {url}...")

try:
    # Send a dummy request with fake data
    response = requests.post(url, json={
        "gtin": "1234567890",
        "department": "DECANT.WS.1"
    })
    print("Connected successfully.")
    print(f"Status code: {response.status_code}")
    print("Response:")
    print(response.text)
except requests.exceptions.ConnectionError as e:
    print("Connection failed.")
    print("Error:", e)
except Exception as e:
    print("Unexpected error.")
    print("Error:", e)