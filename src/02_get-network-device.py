import json
import requests

#api_url_login = "http://localhost:58000/api/v1/ticket"

#headers_login = {
#    "content-type": "application/json"
#}


#body_json = {
#    "username": "cisco",
#    "password": "class"
#}

#resp = requests.post(api_url_login, json.dumps(body_json_login), headers=headers_login)

#response_json_login = resp.json()

api_url = "http://localhost:58000/api/v1/network-device"

#headers={"X-Auth-Token": response_json["response"]["serviceTicket"]}

headers={"X-Auth-Token": "NC-5-21dab29d0df44e19a3e2-nbi"}

resp = requests.get(api_url, headers=headers)

print("Request status: ", resp.status_code)

response_json = resp.json()
print()
print()
print (response_json)
print()
print()
networkDevices = response_json["response"]

for networkDevice in networkDevices:
    print(networkDevice["hostname"], "\t", networkDevice["platformId"], "\t", networkDevice["managementIpAddress"])
