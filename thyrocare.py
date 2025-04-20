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


#api_key=get_thyrocare_token()
url_products='https://velso.thyrocare.cloud/api/productsmaster/Products'
url = 'https://velso.thyrocare.cloud/api/Login/Login'


#db configuration
host = os.getenv('hostname')
user = os.getenv('user')
password = os.getenv('password')
database = os.getenv('database')
auth_plugin = os.getenv('auth_plugin')

def get_thyrocare_token():
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
      "username": os.getenv('tc_username'),
      "password": os.getenv('tc_password'),
      "portalType": "",
      "userType": os.getenv('tc_userType')
  }
  
  response=requests.post(url=url,json=data, headers=headers)
  api_token_key=response.json()['apiKey']
  #print(api_token_key)
  return api_token_key

def get_thyrocare_products():
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
      "Apikey": get_thyrocare_token(),
      "ProductType": "All"
  }
  
  response = requests.post(url=url_products,json=data, headers=headers)
  
  
  # with open('all_tests_products.csv','w') as f:
  #   for item in response.json().get('master').get('tests',[]):
  #     f.write(item['rate']['b2C']+"*"+item['rate']['offerRate'] +"*"+item['name']+"*"+item['code']+'\n')
  # print("all products retrieved successfully")
  return response.json()



def update_db_thyrocare_products():
  offer_products = get_thyrocare_products()
  print("all products retrieved successfully")
  connection = mysql.connector.connect(host=host, user=user, password=password, database=database, auth_plugin=auth_plugin)
  cursor = connection.cursor()
  
  print("connection made with database successfully")
  
  #deleting records from the table before inserting new records
  delete_query = "DELETE FROM thyrocare_tests"
  cursor.execute(delete_query)
  connection.commit()
  
  
  for item in offer_products.get('master').get('offer',[]):
    #print(item['code']+item['name']+item['type']+item['rate']['b2C']+item['rate']['offerRate']+item['margin']+item['fasting'])
    query = "INSERT IGNORE INTO thyrocare_tests (tc_prod_id, tc_prod_name,tc_prod_type,tc_prod_childs,tc_test_Count,tc_rate_b2c,tc_rate_offer,tc_margin,tc_fasting) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (item['code'], item['name'], item['type'], json.dumps(item['childs']), item['testCount'], item['rate']['b2C'], item['rate']['offerRate'], item['margin'], item['fasting']))
    connection.commit()
    
  for item in offer_products.get('master').get('tests',[]):
    #print(item['code']+item['name']+item['type']+item['rate']['b2C']+item['rate']['offerRate']+item['margin']+item['fasting'])
    query = "INSERT IGNORE INTO thyrocare_tests (tc_prod_id, tc_prod_name,tc_prod_type,tc_prod_childs,tc_test_Count,tc_rate_b2c,tc_rate_offer,tc_margin,tc_fasting) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (item['code'], item['name'], item['type'], json.dumps(item['childs']), item['testCount'], item['rate']['b2C'], item['rate']['offerRate'], item['margin'], item['fasting']))
    connection.commit()
  
  for item in offer_products.get('master').get('profile',[]):
    #print(item['code']+item['name']+item['type']+item['rate']['b2C']+item['rate']['offerRate']+item['margin']+item['fasting'])
    query = "INSERT IGNORE INTO thyrocare_tests (tc_prod_id, tc_prod_name,tc_prod_type,tc_prod_childs,tc_test_Count,tc_rate_b2c,tc_rate_offer,tc_margin,tc_fasting) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (item['code'], item['name'], item['type'], json.dumps(item['childs']), item['testCount'], item['rate']['b2C'], item['rate']['offerRate'], item['margin'], item['fasting']))
    connection.commit()
    
  connection.close()
  cursor.close()
  print("thyrocare products inserted successfully")
  

def get_thyrocare_test_detail(productcode):
  all_products = get_thyrocare_products()
  
  for item in all_products.get('master').get('offer',[]):
    if item['code']==productcode:
      for test in item['childs']:
        print(test['name'])
        print(test['code'])
        print(test['groupName'])
        print(test['type'])




def check_pincode_availability_thyrocare(pincode):
  if len(pincode) != 6:
    return {"response": "Failure", "message": "Invalid pincode"}
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
      "Apikey": get_thyrocare_token(),
      "Pincode": f"{pincode}"
  }
  
  response = requests.post(url='https://velso.thyrocare.cloud/api/TechsoApi/PincodeAvailability',json=data, headers=headers)
  #print(response.json())
  try:
    if response.json()['status'] == 'Y':
      return response.json()
    else:
      return {"status": "N", "message": "Pincode not available"}
    
  except KeyError:
    return {"status": "N", "message": "Pincode not available"}


def check_slots_availability_thyrocare(pincode,booking_dt,test_id):
  headers = {
      'Content-Type': 'application/json',
      'Cookie': 'ARRAffinity=d45f3e41a57738967561c580e540208a1117a87753342792901a;ARRAffinity=3666eec51755029e95841e4cad76b639868f03fb2c9e42e8d4970cd42b2a34ea;ARRAffinitySameSite=3666eec51755029e95841e4cad76b639868f03fb2c9e42e8d4970cd42b2a34ea; ApplicationGatewayAffinity=6fed3da3fc0148fcd8fbf1a27ec431a5;ApplicationGatewayAffinityCORS=6fed3da3fc0148fcd8fbf1a27ec431a5'
  }
  
      # Generate Items dynamically from test_ids list
  items = []
  for tid in test_id:
      items.append({
          "Id": tid,
          "PatientQuantity": 1,
          "PatientIds": [1]
      })
  data = {
      "Apikey": get_thyrocare_token(),
      "Pincode": f"{pincode}",
      "Date": f"{booking_dt}",
      "BenCount":1,
      "Patients": [
          {
            "Id": 1,
            "Name": "Test",
            "Gender": "M",
            "Age": 25,
          }
          ],
      
      "Items": items
      
      }
  
  response = requests.post(url='https://velso.thyrocare.cloud/api/TechsoApi/GetAppointmentSlots',json=data, headers=headers)
  #print(response.json())
  return response.json()


def view_cart_details_thyrocare(products,rates,report_required):
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
      "Apikey": get_thyrocare_token(),
      
      "Products":f"{products}",
      "Rates":f"{rates}",

      "ClientType":"PUBLIC",
      "Mobile":"7869734430",
      "BenCount":"1",
      "Report":f"{report_required}",
      "Discount":""
  }
  
  response = requests.post(url='https://velso.thyrocare.cloud/api/CartMaster/DSAViewCartDTL',json=data, headers=headers)
  print(response.json())
  return response.json()


def create_order_thyrocare(products,pincode,report_required,name, age, gender,phone, email,address,date, time,order_id):
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
      "api_key": get_thyrocare_token(),

      "ref_order_id":f"{order_id}",
      "email":f"{email}",
      "mobile":f"{phone}",
      "address":f"{address}",
      "appt_date":f"{date} {time}",
      "order_by":"Customer",
      "passon":0,
      "pay_type":"POSTPAID",
      "pincode":f"{pincode}",
      "products":f"{products}",
      "ref_code":"7869734430",
      "remarks":"testentry",
      "reports":f"{report_required}",
      "service_type":"HOME",
      "ben_data": [
      {
      "name":f"{name}",
      "age":f"{age}",
      "gender":f"{gender}"
      }
      ],
      "coupon":"",
      "order_mode":"DSA-BOOKING-API",
      "collection_type":"",
      "source":"GoelHealthCare",
  }
  
  
  response = requests.post(url='https://dx-dsa-service.thyrocare.com//api/booking-master/v2/create-order',json=data, headers=headers)
  #print(response.json())
  return response.json()


def get_order_summary_thyrocare(order_no):
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
      "Apikey": get_thyrocare_token(),
      "OrderNo":f"{order_no}"

  }
  
  response = requests.post(url='https://velso.thyrocare.cloud/api/OrderSummary/OrderSummary',json=data, headers=headers)
  print('api accessed successfully')
  #print(response.json())
  # print(response.json()['orderMaster'][0])
  # print(response.json()['orderMaster'][0]['status'])
  
  return response.json()

def cancel_order_thyrocare(order_no,reason):
  headers = {
      'Content-Type': 'application/json',
      'Cookie': ''
  }
  data = {
    "ApiKey": get_thyrocare_token(),
    "OrderNo": f"{order_no}",
    "CancellationReason": f"{reason}"
  }
  
  response = requests.post(url='https://velso.thyrocare.cloud/api/OrderMaster/OrderCancellation',json=data, headers=headers)
  print(response.json())
  return response.json()

def get_b2capi_access_token():
  headers = {
      'Content-Type': 'application/json'
  }
  
  USERNAME= "7869734430"
  PASSWORD= "Baby@2023"
  
  
  response = requests.get(url=f'https://b2capi.thyrocare.com/APIS/COMMON.svc/{USERNAME}/{PASSWORD}/portalorders/DSA/Login', headers=headers)
  print(response.json())
  api_token_key=response.json()['API_KEY']
  #print(api_token_key)
  return api_token_key    


def report_download_thyrocare(lead_id,mobile):
  headers = {
      'Content-Type': 'application/json'
  }
  B2CAPIKEY = '2oVtJaTDWS3VBOhzQcdZ9v1OCgEdhAtNf0unh8fpQNYcKLWvXyFzEw=='
  #print(B2CAPIKEY)
  LEADID=lead_id
  MOBILE=mobile
  ReportFormat='PDF'
  response = requests.get(url=f'https://b2capi.thyrocare.com/APIS/order.svc/{B2CAPIKEY}/GETREPORTS/{LEADID}/{ReportFormat}/{MOBILE}/Myreport')
  print(response.json())
  return response.json()
     
#get_thyrocare_token()

#{'response_status': 1, 'response': {'message': 'Order Placed Successfully', 'duplicate_skus': None}, 'ben_data': [{'name': 'None', 'age': 23, 'gender': 'Male', 'lead_id': 'SP80994962'}], 'order_no': 'VLA0BE52', 'products': 'HBST', 'product_names': 'HBST', 'service_type': 'HOME COLLECTION', 'mode': 'PAY WHILE SAMPLE COLLECTION', 'report_hard_copy': 'YES', 'customer_rate': 1032, 'booked_by': 'Test', 'status': 'YET TO CONFIRM', 'pay_type': 'POSTPAID', 'mobile': '7381062885', 'address': 'Flat 304, Block H, JAINS CARLTON CREEK, Lanco Hills Road Flat 304, Block H, JAINS CARLTON CREEK, Lanco Hills Road', 'email': 'mohanmurali.behera@gmail.com', 'ref_order_id': 'NIRVIYU30', 'fasting': 'NON FASTING', 'collection_centers': None, 'qr': None}

#report_download_thyrocare("SP81032410","7381062885")

# data = {
#       "username": "7869734430",
#       "password": "Baby@2023",
#       "portalType": "",
#       "userType": "DSA"
#   }

#cancel_order_thyrocare('VL1377AC','TEST')

#{'respId': 'SUCCESS', 'response': 'Order cancelled successfully'}

#get_order_summary_thyrocare('VLDEE802')
# {
#   ''respId'': ''RES00001'',
#   ''response'': ''Success'',
#   ''mergedOrderNos'': None,
#   ''orderMaster'': [
#     {
#       ''orderNo'': ''VLDEE802'',
#       ''ids'': ''SP80969646'',
#       ''names'': ''SAGARTEST'',
#       ''products'': ''UPTR'',
#       ''serviceType'': ''HOMECOLLECTION'',
#       ''payType'': ''POSTPAID'',
#       ''rate'': ''506'',
#       ''bookingThrough'': ''GOELHEALTHCARE'',
#       ''address'': ''h-304,
#       jainscarltoncreek,
#       khajaguda,
#       hyderabad,
#       500089'',
#       ''pincode'': ''500089'',
#       ''remarks'': ''ORDERBASED-NEWRATE~testentry'',
#       ''status'': ''YETTOASSIGN'',
#       ''tsp'': '''',
#       ''appointmentId'': None,
#       ''patinetId'': None,
#       ''incentive'': ''60'',
#       ''cancelRemarks'': '''',
#       ''ulc'': '''',
#       ''refByDRName'': '''',
#       ''cmlt'': ''0'',
#       ''feedback'': ''N'',
#       ''email'': ''mohanmurali.behera@gmail.com'',
#       ''mobile'': ''7381062885''
#     }
#   ],
#   ''leadHistoryMaster'': [
#     {
#       ''bookedOn'': [
#         {
#           ''leadId'': ''SP80969646'',
#           ''date'': ''12-04-202512: 14''
#         }
#       ],
#       ''assignTspOn'': [
#         {
#           ''leadId'': ''SP80969646'',
#           ''date'': ''14-04-202512: 00''
#         }
#       ],
#       ''appointOn'': [
#         {
#           ''leadId'': ''SP80969646'',
#           ''date'': ''14-04-202512: 00''
#         }
#       ],
#       ''reappointOn'': [
        
#       ],
#       ''servicedOn'': None,
#       ''reportedOn'': None,
#       ''deliverdOn'': [
        
#       ],
#       ''rejectedOn'': None
#     }
#   ],
#   ''benMaster'': [
#     {
#       ''name'': ''SAGARTEST'',
#       ''id'': ''SP80969646'',
#       ''age'': ''30'',
#       ''gender'': ''F'',
#       ''mobile'': ''7381062885'',
#       ''status'': ''YETTOASSIGN'',
#       ''url'': None,
#       ''reminder'': ''NO'',
#       ''barcode'': ''''
#     }
#   ],
#   ''tspMaster'': [
#     {
#       ''tsp'': '''',
#       ''email'': ''mohanmurali.behera@gmail.com'',
#       ''landline'': '''',
#       ''mobile'': ''7381062885'',
#       ''bctName'': '''',
#       ''bctMobile'': ''''
#     }
#   ],
#   ''qr'': None,
#   ''collectionCenters'': None,
#   ''phleboDetail'': {
#     ''phleboNumber'': None,
#     ''phleboName'': None
#   }
# }
 
#view_cart_details_thyrocare('UPTR','231',1,1)
# {
#   ''respId'': ''RES00001'',
#   ''userType'': ''LOYALTY'',
#   ''response'': ''Success'',
#   ''product'': ''UPTR'',
#   ''rates'': ''231'',
#   ''payable'': ''431'',
#   ''margin'': ''60'',
#   ''onlineDiscount'': ''0'',
#   ''loyaltyDiscount'': ''0'',
#   ''homeVisitDiscount'': None,
#   ''collectCharge'': ''0'',
#   ''homeVisitCharge'': ''0'',
#   ''testingCharges'': ''231'',
#   ''benMin'': ''1'',
#   ''benMax'': ''10'',
#   ''benMultiple'': ''1'',
#   ''hcrInclude'': ''N'',
#   ''apptBlock'': None,
#   ''hcrAmount'': 75,
#   ''note'': '''',
#   ''isPrepaidAllow'': ''Y'',
#   ''isABTest'': None,
#   ''cmlt'': None,
#   ''chcCharges'': ''200'',
#   ''chcLabel'': ''ServiceCharges'',
#   ''allowedBookingsDays'': ''7'',
#   ''chcNote'': ''Note: AdditionalcollectionchargeofRs200willbeapplicableiftheorderamountislessthanRs300.''
# }
#create_order_thyrocare('UPTR','500089','Y')
# {
#   ''response_status'': 1,
#   ''response'': {
#     ''message'': ''OrderPlacedSuccessfully'',
#     ''duplicate_skus'': None
#   },
#   ''ben_data'': [
#     {
#       ''name'': ''SagarTest'',
#       ''age'': 30,
#       ''gender'': ''Female'',
#       ''lead_id'': ''SP80969646''
#     }
#   ],
#   ''order_no'': ''VLDEE802'',
#   ''products'': ''UPTR'',
#   ''product_names'': ''UPTR'',
#   ''service_type'': ''HOMECOLLECTION'',
#   ''mode'': ''PAYWHILESAMPLECOLLECTION'',
#   ''report_hard_copy'': ''YES'',
#   ''customer_rate'': 506,
#   ''booked_by'': ''Test'',
#   ''status'': ''YETTOCONFIRM'',
#   ''pay_type'': ''POSTPAID'',
#   ''mobile'': ''7381062885'',
#   ''address'': ''h-304,
#   jainscarltoncreek,
#   khajaguda,
#   hyderabad,
#   500089'',
#   ''email'': ''mohanmurali.behera@gmail.com'',
#   ''ref_order_id'': ''NIRVIYU29'',
#   ''fasting'': ''NONFASTING'',
#   ''collection_centers'': None,
#   ''qr'': None
# }
#check_slots_availability_thyrocare("500089",'2025-04-14',['AFP-C','UPTR'])


# # Storing the tests list as a JSON string
# tests = ["CBC", "Lipid Profile", "Thyroid Panel"]
# tests_json = json.dumps(tests)
# print(json.load(tests_json))

# import requests

# image_url = "https://b2capi.thyrocare.com/API_Beta/Images/B2C/OFFERS/PROJ1024559/SMOKERS PANEL BASIC_INDEX.JPG/1"
# response = requests.get(image_url)

# if response.status_code == 200:
#     with open("smokers_panel_basic.jpg", "wb") as file:
#         file.write(response.content)
#     print("Image downloaded successfully!")
# else:
#     print("Failed to retrieve image.")
