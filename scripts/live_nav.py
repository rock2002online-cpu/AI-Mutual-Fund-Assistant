import requests

url = "https://www.amfiindia.com/spages/NAVAll.txt"

response = requests.get(url)

print("Status Code:", response.status_code)

if response.status_code == 200:
    print("\nFirst 20 lines of the file:\n")

    lines = response.text.splitlines()

    for line in lines[:20]:
        print(line)
else:
    print("Unable to download NAV data.")
    