import requests

FOLDER = "inbox"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
# PROXIES = {"http": "socks5://user:pass@host:port", "https": "socks5://user:pass@host:port"}
CLIENT_ID = "8b4ba9dd-3ea5-4e5f-86f1-ddba2230dcf2"
REFRESH_TOKEN = "M.C557_BAY.0.U.-CgCmeAr6JYwKNhNbbTs9xUYA3nOoUR7R2E!aDc3aUIMlkWzS6S45I15gk8sIAE7c0IOqdEWLMGM1QiFMB4JDiK*aoKHsB79g1pG6xDPBjXFicoge*QqBHI6sRVjtCJD8IIv8YQEN9WsskLNPu4ra5rCHTihEKFzQARwzRa95Hsu0IQiysVqnG5bT6xGxvg6P1xX9z2Fyg1I0tKuTnZdgXCB8!gb6GWJAUiKcrYtK9zrXKlMKq1YguTf*fW2YoWpXt9fZs2lhc8*XCc6pWDdB6XmEVgl7r2aYBGpHwuCROn6*5BkS2OFvqfB7A9uZuEkq!ntqaF!WhngAmycsdelo1kHL8fYNOO*QK42Uo9uh1u6FVlRBiY7huu*r9bSa70p8JgFg7PnsM6l7OUMuwMzRdjo$"

# Obtain access_token via refresh_token for Microsoft Graph scopes.
payload = {"client_id": CLIENT_ID,
           "grant_type": "refresh_token",
           "refresh_token": REFRESH_TOKEN,
           "scope": "https://graph.microsoft.com/.default"}
headers = {"Content-Type": "application/x-www-form-urlencoded"}
# response = requests.post(TOKEN_URL, data=payload, headers=headers, proxies=PROXIES)
response = requests.post(TOKEN_URL, data=payload, headers=headers)
access_token = response.json().get("access_token")

# Read messages from Inbox using Microsoft Graph API access.
url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{FOLDER}/messages"
headers = {"Authorization": f"Bearer {access_token}"}
# response = requests.get(url, headers=headers, proxies=PROXIES)
response = requests.get(url, headers=headers)
messages = response.json().get("value", [])

# Print messages
for msg in messages:
    print(f"From: {msg.get('from', {}).get('emailAddress', {}).get('address')}")
    print(f"Subject: {msg.get('subject')}")
    print(f"Body: {msg.get('body', {}).get('content', '')}")