import requests
import json
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import hashlib
import hmac
import datetime
import time
import logging
from healthians import get_products_by_zipcode

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determine the environment (default: development)
env = os.getenv('FLASK_ENV', 'prod')

# Load the corresponding .env file
dotenv_file = f".env.{env}"

load_dotenv(dotenv_file)

# This function retrieves an access token from the Healthians API using basic authentication.
def healthians_get_access_token():
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getAccessToken"
    headers = {
        'Content-Type': 'application/json'
    }
    auth = HTTPBasicAuth(os.getenv('healthians_username'), os.getenv('healthians_password'))

    response = requests.get(url, headers=headers, auth=auth)
    
    print(response.json()['access_token'])
    
    if response.status_code == 200 :
        return response.json().get('access_token')
    else:
        raise Exception(f"Failed to get token: {response.status_code} - {response.text}")
    
def save_zipcodes_to_db():
    types=['','package','profile']
    for type in types:
        response = get_products_by_zipcode(495001,type)
        print(response['data_count'])
    
#save_zipcodes_to_db()