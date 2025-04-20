import requests
import json
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Determine the environment (default: development)
env = os.getenv('FLASK_ENV', 'prod')

# Load the corresponding .env file
dotenv_file = f".env.{env}"

load_dotenv(dotenv_file)


# call api to get the token from healthians api
import os
import json
import requests
from requests.auth import HTTPBasicAuth

# This function retrieves an access token from the Healthians API using basic authentication.
def healthians_get_access_token():
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getAccessToken"
    headers = {
        'Content-Type': 'application/json'
    }
    auth = HTTPBasicAuth(os.getenv('healthians_username'), os.getenv('healthians_password'))

    response = requests.get(url, headers=headers, auth=auth)
    
    #print(response.json()['access_token'])
    
    if response.status_code == 200 :
        return response.json().get('access_token')
    else:
        raise Exception(f"Failed to get token: {response.status_code} - {response.text}")

# this function retrieves the servicable zip codes from the healthians api
def healthians_get_servicable_zipcodes():
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getActiveZipcodes"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    response = requests.get(url, headers=headers)
    print(f"Response from Healthians API: {response.status_code} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get zipcodes: {response.status_code} - {response.text}")

# this function saves the zip codes to the database
def save_zipcodes_to_db():
    zipcodes = healthians_get_servicable_zipcodes()
    print(type(zipcodes))  # Debugging output

    if isinstance(zipcodes, dict):  
        zipcodes = list(zipcodes.values())  # Convert dict values to a proper list
    
    try:
        connection = mysql.connector.connect(
            host=os.getenv('hostname'),
            database=os.getenv('database'),
            user=os.getenv('user'),
            password=os.getenv('password'),
            auth_plugin=os.getenv('auth_plugin')
        )

        if connection.is_connected():
            cursor = connection.cursor()
            for zipcode in zipcodes:
                if isinstance(zipcode, dict) and 'zipcode' in zipcode:  # Ensure zipcode is a dictionary
                    cursor.execute("INSERT INTO healthians_zipcodes (zipcode) VALUES (%s)", (zipcode['zipcode'],))
            connection.commit()
            print("Zipcodes saved to database successfully.")

    except Error as e:
        print(f"Error while connecting to MySQL: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


# check serviability by lat long coordinates
def check_serviability_by_lat_long(lat, long):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/checkServiceabilityByLocation_v2"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {
        "lat": lat,
        "long": long
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to check servicability: {response.status_code} - {response.text}")


# this funtions gives the coordinates of the address using google api
def get_lat_long(address):
    api_key = os.getenv('GOOGLE_API_KEY')
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    response = requests.get(url)
    data = response.json()
    #print(f"Response from Google API: {data} ")
    if data['status'] == 'OK':
        location = data['results'][0]['geometry']['location']
        print(f"Coordinates for {address}: {location['lat']}, {location['lng']}")  # Debugging output
        return location['lat'], location['lng']
    return None, None



# this function gets slots for a give lat long and date and zone_id

def get_slots_by_lat_long(lat, long, date, zone_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getSlotsByLocation"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {
        "lat": lat,
        "long": long,
        "slot_date": date,
        "zone_id": zone_id
    }
    print(f"Request data: {data} ")  # Debugging output
    response = requests.post(url, headers=headers, json=data)
    print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get slots: {response.status_code} - {response.text}")
    
    




# l1,l2=get_lat_long("banjara hills,hyderabad")
# res=check_serviability_by_lat_long(l1,l2)
# get_slots_by_lat_long(l1,l2,"2025-05-21",res['data']['zone_id'])


#check_serviability_by_lat_long("17.415156403394082", "78.37116994338342")

# # Example
# address = "Bhawanipatna, odisha"
# api_key = "YOUR_API_KEY"
# lat, lng = get_lat_long(address, os.getenv('GOOGLE_API_KEY'))
# print(lat, lng)

