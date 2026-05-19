import requests

url = "http://localhost:8000/project/create"
data = {
    "project_name": "Test Project",
    "project_code": "TEST-001",
    "opportunity_id": "OPP-123"
}

files = {
    "contract_file": ("contract.pdf", b"dummy pdf content", "application/pdf"),
    "estimation_file": ("estimation.xlsx", b"dummy excel content", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
}

try:
    print("Sending request...")
    response = requests.post(url, data=data, files=files)
    print("Status Code:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
