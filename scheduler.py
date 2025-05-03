from flask_apscheduler import APScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from healthians import save_zipcodes_to_db,get_order_status_healthians,get_reports
from thyrocare import get_order_summary_thyrocare, report_download_thyrocare, update_db_thyrocare_products
import logging
import mysql.connector
import os
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
env = os.getenv('FLASK_ENV', 'prod')
dotenv_file = f".env.{env}"
load_dotenv(dotenv_file)
# Set up logging configuration

logging.basicConfig(level=logging.INFO)
# initialize the scheduler
scheduler = BlockingScheduler()

# SQl Database Configuration #
db_config = {
    'host': os.getenv('hostname'),
    'user': os.getenv('user'),
    'password': os.getenv('password'),
    'database': os.getenv('database'),
    'auth_plugin': os.getenv('auth_plugin')
}


# function to auto updated the orders status for healthians
def auto_update_healthians_status():
    """Check and update healthians order status for all pending shipments"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Fetch all pending orders from the database
    cursor.execute("SELECT healthians_order_no FROM healthians_test_bookings WHERE status != 'Order Cancelled' and status != 'Report Available' and healthians_order_no is not null")
    pending_orders = cursor.fetchall()
    #print(pending_orders)
    #print(type(pending_orders))
    for order in pending_orders:
        response = get_order_status_healthians(order[0])
        #print(type(response))
        if response['resCode'] == 'RES0001': #''respId'': ''RES00001'',
            cursor.execute("select status_desc from healthians_reference_status_tbl where status_code = %s", (response['data']['booking_status'],)) 
            status_desc = cursor.fetchone()
            #print(type(response))
            #print(status_desc[0])
            
            if response['data']:
                cursor.execute("update healthians_test_bookings set status = %s where healthians_order_no = %s", (status_desc[0],response['data']['booking_id']))
                conn.commit()
            
    cursor.close()
    conn.close()
    print("Updated healthians order status for all pending orders.")

# function to auto updated the download url of orders for healthians 
def auto_update_healthians_download_url():
    """Check and update download URL for all pending shipments"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Fetch all pending orders from the database whose download url is null
    cursor.execute("SELECT healthians_order_no,vendor_id,patient_id FROM healthians_test_bookings WHERE report_url is null and status = 'Report Available' and healthians_order_no is not null")
    pending_url = cursor.fetchall()
    
    
    
    #print(pending_orders)
    # iterate through the pending orders and update the download url
    for url in pending_url:
        order_=url[0]
        vendor_id=url[1]
        patient_id=url[2]
        response = get_reports(order_,vendor_id,patient_id)
        #print(type(response))
        if response['status']:
            cursor.execute("update healthians_test_bookings set report_url = %s where healthians_order_no = %s", (response['report_url'],order_))
            
    print("Updated download URL for all pending orders.")

#shiprocket

#shiprocet configurations
SHIPROCKET_API_URL = os.getenv('SHIPROCKET_API_URL')
SR_EMAIL = os.getenv('SR_EMAIL')
SR_PASSWORD = os.getenv('SR_PASSWORD')


# shiprocket  api token generation
def get_shiprocket_token():
    url = f"{SHIPROCKET_API_URL}/auth/login"
    payload = {"email": SR_EMAIL, "password": SR_PASSWORD}
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("token")
    return None

def get_shipping_status(shipment_id):
    """Fetch current shipping status from Shiprocket"""
    token= get_shiprocket_token()
    #print(token)
    #print(shipment_id)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(f"{SHIPROCKET_API_URL}/orders/show/{shipment_id}", headers=headers)
    #print(response.json())
    if response.status_code == 200:
        tracking_data = response.json()
        
        status = tracking_data.get("data", {}).get("status", "Unknown")
        return status
    else:
        return "Error"


#thryocare
# UPDATE SHIPPING STATUS IN MYSQL
def update_shipping_status(order_id):
    """Update shipping status in MySQL"""
    if order_id:

        new_status = get_shipping_status(order_id)
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        # Update MySQL with new status
        update_query = "UPDATE shipment SET status = %s WHERE sr_order_id = %s"
        cursor.execute(update_query, (new_status, order_id))
        conn.commit()

# Function to update shipping status in the database
def auto_update_shipping_status():
    """Check and update shipping status for all pending shipments"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()


    cursor.execute("SELECT sr_order_id FROM shipment WHERE status != 'DELIVERED' or status != 'CANCELED' or status is not null")
    pending_orders = cursor.fetchall()

    for order in pending_orders:
        update_shipping_status(order[0])
    
    cursor.close()
    conn.close()
    print("Updated shipping status for all pending orders.")
    
# function to auto update status in lab tests
def auto_update_lab_status():
    """Check and update lab test status for all pending shipments"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Fetch all pending orders from the database
    cursor.execute("SELECT tc_order_no FROM thyrocare_test_bookings WHERE status != 'Done' and status != 'Serviced' and status != 'PartialServiced' and status != 'CANCELLED' and tc_order_no is not null")
    pending_orders = cursor.fetchall()
    #print(pending_orders)
    #print(type(pending_orders))
    for order in pending_orders:
        response = get_order_summary_thyrocare(order[0])
        #print(type(response))
        if response['respId'] == 'RES00001': #''respId'': ''RES00001'',
            if response['orderMaster']:
                cursor.execute("update thyrocare_test_bookings set status = %s where tc_order_no = %s", (response['orderMaster'][0]['status'],order[0]))
                conn.commit()
            
    cursor.close()
    conn.close()
    print("Updated lab test status for all pending orders.")


# function to auto update the download url in the database
def auto_update_download_url():
    """Check and update download URL for all pending shipments"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Fetch all pending orders from the database whose download url is null
    cursor.execute("SELECT tc_lead_no,mobile FROM thyrocare_test_bookings WHERE report_url is null and (status = 'Done' or status = 'Serviced' or status = 'PartialServiced') and tc_order_no is not null")
    pending_url = cursor.fetchall()
    
    #print(pending_orders)
    # iterate through the pending orders and update the download url
    for url in pending_url:
        response = report_download_thyrocare(url[0],url[1])
        #print(type(response))
        if response['RES_ID'] == 'RES0000':
            cursor.execute("update thyrocare_test_bookings set report_url = %s where tc_lead_no = %s", (response['URL'],url[0]))
            
    print("Updated download URL for all pending orders.")



# Define the job to be scheduled
scheduler.add_job(
    id='save_zipcodes_job',
    func=save_zipcodes_to_db,
    trigger='cron',
    hour=11,
    minute=37,
    replace_existing=True,
    max_instances=1
)

scheduler.add_job(
    id='auto_update_healthians_status_job',
    func=auto_update_healthians_status,
    trigger='interval',
    minutes=5,
    replace_existing=True,
    max_instances=1
)

scheduler.add_job(
    id='auto_update_healthians_download_url_job',
    func=auto_update_healthians_download_url,
    trigger='interval',
    minutes=13,
    replace_existing=True,
    max_instances=1
)

scheduler.add_job(id="auto_update_shipping", func=auto_update_shipping_status, trigger="interval",  minutes=5,   replace_existing=True,
    max_instances=1)

scheduler.add_job(id="thyrocare_update", func=update_db_thyrocare_products, trigger="cron", hour=5, minute=30, max_instances=1, replace_existing=True)

scheduler.add_job(id="auto_update_lab_Status", func=auto_update_lab_status, trigger="interval",  minutes=5,   replace_existing=True,max_instances=1)

scheduler.add_job(id="auto_update_download_url", func=auto_update_download_url, trigger="interval",  minutes=5,   replace_existing=True,max_instances=1)

if __name__ == "__main__":
    logging.info("Starting scheduler...")
    scheduler.start()