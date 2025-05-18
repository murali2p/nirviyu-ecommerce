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

import razorpay

#razorpay payment gateway configuration
RAZORPAY_KEY_ID =os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET =os.getenv('RAZORPAY_KEY_SECRET')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET')

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

response = razorpay_client.payment.refund('pay_QWRKZWQX8U1768')

print(response)