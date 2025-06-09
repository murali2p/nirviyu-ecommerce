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
    #print(f"Response from Healthians API: {response.status_code} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get zipcodes: {response.status_code} - {response.text}")

# this function saves the zip codes to the database
def save_zipcodes_to_db():
    zipcodes = healthians_get_servicable_zipcodes()
    #print(type(zipcodes))  # Debugging output
    
    current_time= datetime.datetime.now()

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
            logging.info("Connected to MySQL database")
            cursor = connection.cursor()
            cursor.execute("delete from healthians_zipcodes")
            #print("Deleted existing records from healthians_zipcodes table.")
            connection.commit()
            

            
            for zipcode in zipcodes:
                if isinstance(zipcode, dict) and 'zipcode' in zipcode:  # Ensure zipcode is a dictionary
                    cursor.execute("INSERT IGNORE INTO healthians_zipcodes (zipcode,city_id,state_id) VALUES (%s,%s,%s)", (zipcode['zipcode'],zipcode['city_id'],zipcode['state_id']))
            connection.commit()
            #print("Zipcodes saved to database successfully.")
            
            cursor.execute("SELECT * FROM healthians_zipcodes")
            records = cursor.fetchall()
            
            #deleting records from healthians_products table
            cursor.execute("delete from healthians_products")
            #print("Deleted existing records from healthians_products table.")
            
            for record in records:
                time.sleep(0.25)  # Adding a delay of 0.25 seconds between requests
                types=['','package','profile']
                for type in types:
                    response = get_products_by_zipcode(record[0],type)
                    if response['status'] and response['data']:
                        # Assuming response['data'] is a list of products
                        for product in response['data']:
                            #logging.info(f"start entering products {product['deal_id']}")  # Debugging output
                            #print(product)  # Debugging output
                            #print(f"Product ID: {product['deal_id']}")
                            # Extracting necessary fields from the product
                            cursor.execute("INSERT IGNORE INTO healthians_products (zipcode,test_name,city_name,city_id, price, mrp,product_type,product_type_id,deal_id,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (record[0],product['test_name'],product['city_name'],product['city_id'], product['price'], product['mrp'], product['product_type'], product['product_type_id'], product['deal_id'], current_time))
                            #logging.info(f"End of entering products {product['deal_id']}")
                        connection.commit()
                
                    else:
                        print(f"Failed to get products for zipcode {record[0]}: {response['message']}")
            print("Products saved to database successfully.")
                

    except Error as e:
        print(f"Error while connecting to MySQL: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


# check serviability by lat long coordinates
def check_serviability_by_lat_long(lat, long):
    try:
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
        #print(f"Response from Healthians API: {response.content} ")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to check servicability: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


# this funtions gives the coordinates of the address using google api
def get_lat_long(address):
    address=f"Pincode {address}, India"
    api_key = os.getenv('GOOGLE_API_KEY')
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    response = requests.get(url)
    data = response.json()
    #print(f"Response from Google API: {data} ")
    if data['status'] == 'OK':
        location = data['results'][0]['geometry']['location']
        #print(f"Coordinates for {address}: {location['lat']}, {location['lng']}")  # Debugging output
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
    #print(f"Request data: {data} ")  # Debugging output
    response = requests.post(url, headers=headers, json=data)
    #print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get slots: {response.status_code} - {response.text}")
    

# this function freezes the slot for next 15 mins
def  freeze_slot_by_slot_id(slot_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/freezeSlot_v1"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {
        "slot_id": slot_id,
        "vendor_billing_user_id": "goelhealthcare"
    }

    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        print(f"Response from Healthians API: {response.json()} ")
        return response.json()
    else:
        raise Exception(f"Failed to freeze slot: {response.status_code} - {response.text}")
    

# this function gets the products for a given zip code
def get_products_by_zipcode(zipcode,param):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getPartnerProducts"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {    
        "zipcode": zipcode,
        "product_type": f"{param}",
        "product_type_id": "",
        "limit": "100000"
        
    }
    response = requests.post(url, headers=headers, json=data)
    #print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get products: {response.status_code} - {response.text}")
    

#this function gets the vendor details
def get_vendor_details():
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getVendorIdDetails"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {   
            "mobile_number": 7381062885
                #7869734430  #9993694449
    }
    response = requests.post(url, headers=headers, json=data)
    #print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get vendor details: {response.status_code} - {response.text}")


# this function generates the checksum for the given data and key
def generate_checksum(data, key):
    """
    Generate a checksum using HMAC-SHA256 algorithm.
    :param data: The data for which the checksum is to be generated.
    :param key: The secret key used for generating the checksum.
    :return: The generated checksum.
    """
    hmac_obj = hmac.new(key.encode(), data.encode(), hashlib.sha256)
    return hmac_obj.hexdigest()

# this function places order for a given slot id and product id
def place_order_healthians(patient_id,name,age ,gender,slot_id, product,mobile,billing_name, email, address,lat, long, zipcode,booking_id, vendor_billing_user_id, zone_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/createBooking_v3"
    data = {
    "customer": [
        {
            "customer_id": f"{patient_id}",
            "customer_name": f"{name}",
            "relation": "self",
            "age": age,
            "gender": f"{gender}",
        }
    ],
    "slot": {
        "slot_id": f"{slot_id}"
    },
    "package": [
        {
            "deal_id": product,
        }
    ],
    "customer_calling_number": mobile,
    "billing_cust_name": f"{billing_name}",
    "gender": f"{gender}",
    "mobile": mobile,
    "email": f"{email}",
    "sub_locality": f"{address}",
    "latitude": f"{lat}",
    "longitude": f"{long}",
    "address": f"{address}",
    "zipcode": zipcode,
    "hard_copy": 0,
    "vendor_booking_id": f"{booking_id}",
    "vendor_billing_user_id": f"{vendor_billing_user_id}",
    "payment_option": "cod",
    "zone_id": zone_id
    }
    checksum=generate_checksum(json.dumps(data), os.getenv('X-Checksum'))
    #print(f"Checksum: {checksum}")  # Debugging output
    # data['checksum'] = checksum
    headers = {
        'Content-Type': 'application/json',
        'Authorization  ': f"Bearer {healthians_get_access_token()}",
        'X-Checksum': checksum
        
    }   
    
    
    response = requests.post(url, headers=headers, json=data)
    resp_data = response.json()
    #print(f"Response from Healthians API: {response.json()} ")
    if resp_data:
        #print(f"Response from Healthians API: {resp_data} ")  # Debugging output
        return response.json()
    else:
        raise Exception(f"Failed to place order: {response.status_code} - {response.text}")

def cancel_order(booking_id, vendor_user_id, customer_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/cancelBooking"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {    
        "booking_id": booking_id,
        "vendor_billing_user_id": vendor_user_id,
        "vendor_customer_id": customer_id,
        "remarks": "Customer not available"
    }
    response = requests.post(url, headers=headers, json=data)
    #print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to cancel order: {response.status_code} - {response.text}")

def get_reports(booking_id, vendor_id, customer_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getCustomerReport_v2"
    headers = {
       'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    
    data ={
        'booking_id':booking_id,
        'vendor_billing_user_id': vendor_id,
        'vendor_customer_id': customer_id,
        'allow_partial_report': 1
        
    }
    
    response = requests.post(url, headers=headers, json=data)
    #print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to cancel order: {response.status_code} - {response.text}")

def get_product_details(product_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getProductDetails"
    
    deal_type, deal_id = product_id.split("_")
    headers = {         
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {
        "deal_type": deal_type,  
        "deal_type_id": deal_id
    }
    response = requests.post(url, headers=headers, json=data)
    
    # create a csv file to save the product details with the product_id as the filename and have columsn that take id and name from the response data
    if response.status_code == 200:
        product_details = response.json()
        #print(f"Product details: {product_details}")  # Debugging output
        # Save product details to a CSV file
        filename = f"{product_details['data']['name']}_{product_id}.csv"
        with open(filename, 'w') as file:
            file.write("id,name\n")
            for item in product_details['data']['constituents']:
                file.write(f"{item['id']},{item['name']}\n")
        print(f"Product details saved to {filename}")
    
    
    print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get product details: {response.status_code} - {response.text}")
        

def get_order_status_healthians(booking_id):
    url = f"{os.getenv('healthians_base_url')}/goelhealthcare/getBookingStatus"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {healthians_get_access_token()}"
    }
    data = {
        "booking_id": booking_id
    }
    response = requests.post(url, headers=headers, json=data)
    #print(f"Response from Healthians API: {response.json()} ")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get order status: {response.status_code} - {response.text}")


#get_order_status_healthians("1387705994324")

#get_product_details("parameter_34")        
        
#get_reports("1387705970615")        
    


#place_order()
#Response from Healthians API: {'status': True, 'message': 'Booking (1387705970615) placed successfully.', 'lead_id': 0, 'booking_id': '1387705970615', 'resCode': 'RES0001'}
#healthians_get_access_token()
#Response from Healthians API: {'status': True, 'message': 'Booking (1387705994324) placed successfully.', 'lead_id': 0, 'booking_id': '1387705994324', 'resCode': 'RES0001'}
#get_vendor_details()
#Response from Healthians API: {'status': True, 'message': 'Data available!', 'data': {'customer_name': 'Mohan', 'age': '0', 'gender': 'M', 'vendor_user_id': 'mohan123', 'family_members_data': [{'vendor_user_id': '123', 'name': 'RAHUL SHARMA', 'gender': 'M', 'age': '31'}]}, 'code': 200}

#get_products_by_zipcode("500002")

# l1,l2=get_lat_long("122001")
# res=check_serviability_by_lat_long(l1,l2)
# get_slots_by_lat_long(l1,l2,"2025-04-27",res['data']['zone_id'])

#freeze_slot_by_slot_id("34704496")


#check_serviability_by_lat_long("1", "8")

# # Example
# address = "Bhawanipatna, odisha"
# api_key = "YOUR_API_KEY"
# lat, lng = get_lat_long(address, os.getenv('GOOGLE_API_KEY'))
# print(lat, lng)

#save_zipcodes_to_db()
#get_products_by_zipcode(403601)
#healthians_get_access_token()
#get_product_details("package_1818")

