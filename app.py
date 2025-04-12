from flask import Flask, request, jsonify, render_template,session,redirect,url_for,abort,flash
from flask_login import login_user, LoginManager, login_required, UserMixin, logout_user, current_user
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import InputRequired, Length, ValidationError,Email
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import razorpay
from datetime import timedelta
import datetime
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from rapidfuzz import process,fuzz
import requests,json
from flask_apscheduler import APScheduler
from thyrocare import get_thyrocare_products,get_thyrocare_test_detail,check_pincode_availability_thyrocare



# Determine the environment (default: development)
env = os.getenv('FLASK_ENV', 'prod')

# Load the corresponding .env file
dotenv_file = f".env.{env}"

load_dotenv(dotenv_file)

app = Flask(__name__)  # create a new Flask app
# app.secret_key = 'your_secret_key' 
app.config['SECRET_KEY']= os.getenv('SECRET_KEY')
# # Set a longer session lifetime (e.g., 30 minutes)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
# # upload config
# app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['UPLOAD_FOLDER'] =os.getenv('UPLOAD_FOLDER')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
# Check if uploaded file is an image
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#razorpay payment gateway configuration
RAZORPAY_KEY_ID =os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET =os.getenv('RAZORPAY_KEY_SECRET')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET')

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# initialize the scheduler
scheduler = APScheduler()

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

# Schedule the job every 10 minutes
scheduler.add_job(id="auto_update_shipping", func=auto_update_shipping_status, trigger="interval", minutes=50)
scheduler.start()


# SQl Database Configuration #
db_config = {
    'host': os.getenv('host'),
    'user': os.getenv('user'),
    'password': os.getenv('password'),
    'database': os.getenv('database'),
    'auth_plugin': os.getenv('auth_plugin')
}


# email configuration

app.config['MAIL_SERVER'] = 'smtpout.secureserver.net'
app.config['MAIL_PORT'] = 465  # For TLS
# Alternatively, you can use port 465 for SSL
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
recipients = ['mohanmurali.behera@gmail.com']

#initialize the Mail

mail = Mail(app)

#reCaptcha configuration
RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY = os.getenv('RECAPTCHA_PRIVATE_KEY')
verify_url= os.getenv('verify_url')

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
#getting the order items
def get_order_items(order_id):
    """Fetch order items from the database for a given order_id."""
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    
    query = "select p.prod_name as product_name, p.sku as sku,o.qty as quantity, cast((p.price * (1-(p.discount/100))) as decimal(10,2)) as final_price,p.discount as discount,round(((p.price * (1-(p.discount/100))) / 1.18), 2) as taxable_price,round((((p.price * (1-(p.discount/100))) / 1.18)+(p.price*p.discount/100))*1.18,2) as selling_price,round((p.price*p.discount/100)*1.18,2) as item_discount  from orders as o inner join products as p on o.prod_id=p.prod_id where order_id=%s" #review this query to get the order items
    cursor.execute(query, (order_id,))
    items = cursor.fetchall()
    print("getting order items")
    print(items)
    cursor.close()
    connection.close()
    
    # Convert items into Shiprocket format
    order_items = [
        {
            "name": item["product_name"],
            "sku": item["sku"],
            "units": item["quantity"],
            "selling_price": float(item["selling_price"]),
            "discount": float(item["item_discount"]),
            "tax": 18 
        }
        for item in items
    ]
    
    print(order_items)
    
    return order_items


# Function to store shipment details in MySQL
def save_shipment_to_db(order_id, shiprocket_response):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        sr_order_id = shiprocket_response.get("order_id", None)
        shipment_id = shiprocket_response.get("shipment_id", None)
        awb_code = shiprocket_response.get("awb_code", None)
        courier_name = shiprocket_response.get("courier_name", None)
        status = shiprocket_response.get("status", None)

        query = """
            INSERT INTO shipment (internal_order_id, sr_order_id,shipment_id, awb_code, courier_name, status)
            VALUES (%s,%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (order_id, sr_order_id, shipment_id, awb_code, courier_name, status))
        connection.commit()
        cursor.close()
        connection.close()
        print("Shipment saved successfully")
        return True
    except Exception as e:
        print(f"Error saving shipment: {e}")
        return False

def create_shiprocket_order(order_details):
    token = get_shiprocket_token()
    if not token:
        return {"error": "Authentication failed"}
    
    order_items = get_order_items(order_details["order_id"])
    
    url = f"{SHIPROCKET_API_URL}/orders/create/adhoc"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "order_id": order_details["order_id"],
        "order_date": order_details["order_date"],
        "pickup_location": "Office",
        "channel_id": "",
        "billing_customer_name": order_details["customer_name"],
        "billing_last_name": "",
        "billing_address": order_details["billing_address"],
        "billing_city": order_details["billing_city"],
        "billing_pincode": order_details["billing_pincode"],
        "billing_state": order_details["billing_state"],
        "billing_country": "India",
        "billing_email": order_details["email"],
        "billing_phone": order_details["phone"],
        "shipping_is_billing": True,
        "order_items": order_items,
        "payment_method": "Prepaid",
        "sub_total": float(order_details["sub_total"]),
        "length": order_details["length"],
        "breadth": order_details["breadth"],
        "height": order_details["height"],
        "weight": order_details["weight"]
    }
    
    print("printing payload")
    print(payload)

    response = requests.post(url, json=payload, headers=headers)
    shiprocket_response = response.json()
    print(shiprocket_response)
    # Save response in shipment table
    save_shipment_to_db(order_details["order_id"], shiprocket_response)
    
    return response.json()

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


@app.template_filter('to_float')
def to_float(value):
    try:
        return float(value)
    except ValueError:
        return 0.0

@app.template_filter('sum_prices')
def sum_prices(cart):
    try:
        return sum(float(item['price']) * item['quantity'] for item in cart)
    except (ValueError, TypeError):
        return 0.0
 
# create login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'   

#user class
class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

#cta-form

class ContactForm(FlaskForm):
    name = StringField('name', validators=[InputRequired(), Length(min=4, max=20)])
    email = EmailField('email', validators=[InputRequired(), Email()])
    message = StringField('message', validators=[InputRequired(),Length(min=10, max=3000)])
    submit = SubmitField('submit')
   
# registration_form
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=20)])
    # email = StringField('Email', validators=[InputRequired(), Email()])
    # phone = StringField('Phone Number', validators=[InputRequired(), Length(min=10, max=15)])
    # age = StringField('Age', validators=[InputRequired()])
    # address1 = StringField('Flat/Street', validators=[InputRequired()])
    # address2 = StringField('Area', validators=[InputRequired()])
    # landmark = StringField('Landmark', validators=[InputRequired()])
    # city = StringField('City', validators=[InputRequired()])
    # state = StringField('State', validators=[InputRequired()])
    # zip = StringField('Zip Code', validators=[InputRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        connection = mysql.connector.connect(**db_config)
        cur = connection.cursor()
        cur.execute("SELECT username FROM users WHERE username = %s", (username.data,))
        user = cur.fetchone()
        if user:
            raise ValidationError('Username already exists.')    
 
 
# Create a form for user login:

class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=4, max=20)])
    submit = SubmitField('Login') 

# create decorator to restrict access
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator

# To load a user from the database by ID, implement this function required by Flask-Login:

@login_manager.user_loader
def load_user(user_id):
    connection = mysql.connector.connect(**db_config)
    cur = connection.cursor()
    cur.execute("SELECT * FROM users WHERE cust_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user:
        return User(id=user[0], username=user[1], password=user[2], role=user[3])
    return None


#Handle Login
@app.route('/login', methods=["GET","POST"])  # define a route
def login():
    form = LoginForm()
    if form.validate_on_submit():
        connection = mysql.connector.connect(**db_config)
        cur = connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (form.username.data,))
        user = cur.fetchone()
        cur.close()
        connection.close()
        
        if user and check_password_hash(user[2], form.password.data):  # user[2] is password in DB
            user_obj = User(id=user[0], username=user[1], password=user[2], role=user[3])
            login_user(user_obj)
            session.permanent = True  # Ensure session persists
            # msg = Message('User Logged in', sender='info@nirviyu.com', recipients=recipients)
            # msg.body = (f'Hi, \n\n User  {current_user.username} has logged. \n This is an auto generated email.Do not Reply.****')
            # mail.send(msg)
            if current_user.role == 'admin':
                return redirect(url_for('index_admin'))
            else:
                return redirect(url_for('index'))
        else:
            return 'user_not_found'
    return render_template('login.html', form=form)

# logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Handle user registration:
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        connection = mysql.connector.connect(**db_config)
        cur = connection.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (form.username.data, hashed_password))
        connection.commit()
        
        # #fetch the user_id from the users
        # cur.execute("SELECT id FROM users WHERE username = %s", (form.username.data,))
        # userid = cur.fetchone()
        # # insert the data into the customers table
        # cur.execute("insert into customers(id, cust_name,email, mobile,age,address1,address2,landmark,city,state,pin) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        #             (userid[0],form.username.data,form.email.data,form.email.data,form.age.data,form.address1.data,form.address2.data,form.landmark.data,form.city.data,form.state.data,form.zip.data,))        
        # connection.commit()
        cur.close()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

 
#routes for the website    

@app.route('/', methods=('GET','POST'))  # define a route
def index():
    form=ContactForm()
    # connect to the MySQL server
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    # execute the SQL query
    cursor.execute('SELECT a.*,b.image_url FROM products as a left join (select * from (select *, rank() over(partition by product_id order by id asc) as Rank_  from product_images) as a where a.Rank_=1) as b on a.prod_id=b.product_id limit 3')
    # fetch the results
    results = cursor.fetchall()
    # close the cursor and the connection
    cursor.close()
    connection.close()
    # return the response

    return render_template('index.html', products=results, recaptcha_key=RECAPTCHA_PUBLIC_KEY, form=form) 

@app.route('/admin', methods=('GET','POST'))  # define a route
@login_required
@roles_required('admin')
def index_admin():

    return render_template('index_admin.html')





@app.route('/products', methods=['GET','POST'])  # define a route
def products():
    try:

        # connect to the MySQL server
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        # execute the SQL query
        cursor.execute('SELECT a.*,b.image_url FROM products as a left join (select * from (select *, rank() over(partition by product_id order by id asc) as Rank_  from product_images) as a where a.Rank_=1) as b on a.prod_id=b.product_id')
        # fetch the results
        results = cursor.fetchall()
        # close the cursor and the connection
        cursor.close()
        connection.close()
        # return the response
        return render_template('products.html', products=results)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/products/<int:id>', methods=['GET','POST'])  # define a route
def product_detail(id):
    try:
        # connect to the MySQL server
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        # getting the details of products
        cursor.execute('SELECT * FROM products WHERE prod_id = %s', (id,))
        # fetch the result
        result = cursor.fetchone()
        
        # getting the details of images
        cursor.execute("SELECT image_url FROM product_images WHERE product_id = %s", (id,))
        images = cursor.fetchall()
        
        
        # close the cursor and the connection
        cursor.close()
        connection.close()
        # return the response
        return render_template('product_details.html', product=result, images=images)
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/add_to_cart/<int:id>', methods=['POST'])
@login_required
def add_to_cart(id):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Fetch the product
        cursor.execute('SELECT * FROM products WHERE prod_id = %s', (id,))
        product = cursor.fetchone()
        if not product:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Product not found'})
        
        # Check if the product is already in the cart
        cursor.execute('SELECT * FROM cart WHERE cust_id = %s AND prod_id = %s', (current_user.id, product['prod_id']))
        cart_item = cursor.fetchone()
        current_time = datetime.datetime.now()
        
        if cart_item:
            # Update the quantity if the product is already in the cart
            cursor.execute(f'UPDATE cart SET qty = qty + 1, updated_at = %s WHERE cust_id = %s AND prod_id = %s', (current_time,current_user.id, product['prod_id']))
        else:
            # Insert the product into the cart if it is not already there
            cursor.execute('INSERT INTO cart (cust_id, prod_id, qty, price, updated_at) VALUES (%s, %s, 1, %s,%s)', (current_user.id, product['prod_id'], product['price'],current_time))
        
        connection.commit()
        
        #update the sub total fiedl in the cart table
        cursor.execute('UPDATE cart SET subtotal = qty * price *(1-(%s/100))  WHERE cust_id = %s and prod_id =%s', (product['discount'],current_user.id,product['prod_id']))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return redirect(url_for('cart'))
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)})
    except Exception as e:
        return jsonify({'error': str(e)})



@app.route('/cart')
@login_required
def cart():
    
    # caculate the total amount
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM cart inner join products on cart.prod_id =products.prod_id inner join (select * from (select *, rank() over(partition by product_id order by id asc) as Rank_  from product_images) as a where a.Rank_=1) as c on c.product_id=products.prod_id WHERE cart.cust_id = %s', (current_user.id,))
    cart = cursor.fetchall()
    #print(cart)
    cursor.close()
    connection.close()
    total_amt = 0
    mrp=0
   
    for item in cart:
        mrp+=item['price']*item['qty']
        total_amt+=item['subtotal']

    discount=mrp-total_amt
    return render_template('cart.html', cart=cart, total_amt=total_amt, mrp=mrp, discount=discount)
 

@app.route('/add_to_order', methods=['POST'])
@login_required
def add_to_order():
   # caculate the total amount
    try:
        

        if not current_user.username:
            flash("Please log in to place an order.", "warning")
            return redirect(url_for('login'))

        address_id = request.form.get('address_id')
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)        
        if address_id:  # User selected an existing address

            cursor.execute("SELECT * FROM addresses WHERE add_id = %s AND user_id = %s", (address_id, current_user.id))
            address = cursor.fetchone()
        else:  # User entered a new address
            full_name = request.form['full_name']
            phone = request.form['phone']
            address_line1 = request.form['address_line1']
            address_line2 = request.form.get('address_line2', '')
            city = request.form['city']
            state = request.form['state']
            postal_code = request.form['postal_code']
            #country = request.form['country']
            email=request.form['email']

            cursor.execute("""
                INSERT INTO addresses (user_id, full_name, phone, address_line1, address_line2, city, state, postal_code, is_default,email)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
            """, (current_user.id, full_name, phone, address_line1, address_line2, city, state, postal_code, True,email))
            connection.commit()
     
            address_id = cursor.lastrowid  # Get the ID of the newly inserted address
            cursor.close()
            connection.close()
            flash("Address added successfully!", "success")
            
        
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM cart inner join products on cart.prod_id =products.prod_id WHERE cart.cust_id = %s', (current_user.id,))
        cart = cursor.fetchall()
        #print(cart)
        total_amt = 0
        for item in cart:
            total_amt+=item['subtotal']
            
        total_qty = 0
        for item in cart:
            total_qty+=item['qty']
            
        weight=0.2*total_qty
        
        
        
        if total_qty>1:
            if total_qty ==2:
                length=10
                width=5
                height=10
            elif total_qty <=4:
                length=10
                width=10
                height=10
            elif total_qty <=6:
                length=15
                width=10
                height=10
            elif total_qty <=8:
                length=20
                width=10
                height=10
            elif total_qty <=10:
                length=25
                width=10
                height=10
            elif total_qty <=15:
                length=25
                width=15
                height=10
            elif total_qty <=20:
                length=25
                width=20
                height=10
            elif total_qty <=40:
                length=25
                width=25
                height=20
            else:
                length=25
                width=25
                height=30
        else:
            length=5
            width=5
            height=10 
        
        #print(total_amt)
    
        current_time = datetime.datetime.now()
        data = { "amount": int(total_amt*100), "currency": "INR", "receipt": "order_rcptid_11" }
        payment = razorpay_client.order.create(data=data)
        # updat the order_generate table
        query = "INSERT INTO order_generate (razorpay_order_id, amount, updated_at) VALUES (%s, %s, %s)"
        cursor.execute(query, (payment['id'], total_amt, current_time))
        connection.commit()
        
        #get the latest order id which is generated with payment[id ]
        cursor.execute('SELECT order_id FROM order_generate WHERE razorpay_order_id = %s', (payment['id'],))
        order_id = cursor.fetchone()
        #print(order_id)
        
        # insert the order_id into the order_checkout table
        query = "INSERT INTO order_checkout (order_id,razorpay_order_id, cust_id, checkout,add_id, total_qty,length, width, height, weight) VALUES (%s, %s,%s, %s,%s,%s,%s,%s,%s,%s)"
        cursor.execute(query, (order_id['order_id'],payment['id'], current_user.id, current_time,address_id,total_qty,length, width, height, weight))
        
        # insert the items in cart into orders table
        for item in cart:
            query = "INSERT INTO orders (order_id,cust_id, prod_id, qty, price, subtotal, cart_updated_at,created_at) VALUES (%s,%s, %s, %s, %s, %s,%s,%s)"
            cursor.execute(query, (order_id['order_id'],current_user.id, item['prod_id'], item['qty'], item['price'], item['subtotal'], item['updated_at'],current_time))
            connection.commit()
            
        # delete the items from the cart
        cursor.execute('DELETE FROM cart WHERE cust_id = %s', (current_user.id,))
        connection.commit()
        cursor.close()
        connection.close()
        #print("the order is placed")
        return redirect(url_for('orders'))
    
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)})
    
@app.route('/remove_from_cart/<int:id>', methods=['POST'])
@login_required

def remove_from_cart(id):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute('DELETE FROM cart WHERE cust_id = %s AND prod_id = %s', (current_user.id, id))
        connection.commit()
        cursor.close()
        connection.close()
        return redirect(url_for('cart'))
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)})
    except Exception as e:
        return jsonify({'error': str(e)})
    
    
# render_template('cart.html', cart=cart, payment=payment)

#     data = { "amount": 20000, "currency": "INR", "receipt": "order_rcptid_11" }
#     payment = razorpay_client.order.create(data=data)
#     print(payment)
#     return render_template('cart.html', cart=session.get('cart', []), payment=payment)

@app.route('/orders', methods=['GET','POST'])
@login_required
def orders():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # GETTING THE LATEST ORDER ID
        query='select orders.order_id  from orders inner join order_generate on orders.order_id = order_generate.order_id where orders.cust_id= %s order by order_generate.updated_at desc limit 1'
        cursor.execute(query,(current_user.id,))
        order_id = cursor.fetchone()
        
  
        # GETTING THE ORDER DETAILS
        cursor.execute('SELECT * FROM orders WHERE order_id = %s', (order_id['order_id'],))
        orders = cursor.fetchall()
       
        
        # getting the payment details
        cursor.execute('SELECT * FROM order_generate WHERE order_id = %s', (order_id['order_id'],))
        payment = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        test_id= os.getenv('RAZORPAY_KEY_ID')
        domain=os.getenv('domain')
        
        return render_template('orders.html',order_id=order_id['order_id'], orders=orders, payment=payment, domain=domain, test_id=test_id)
    except Exception as e:
        return jsonify({'error': str(e)})



@app.route('/payment_success/<int:id>', methods=['POST'])
def payment_success(id):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        data = request.form
        # GETTING THE ORDER DETAILS
        cursor.execute('SELECT og.*,o.cust_id FROM orders as o inner join order_generate as og on o.order_id =og.order_id WHERE o.order_id = %s limit 1', (id,))
        order = cursor.fetchone()
        cursor.close()
        cursor = connection.cursor(dictionary=True)
        #print(order['razorpay_order_id'])
        #print(data['razorpay_order_id'])
        
        if order['razorpay_order_id'] == data['razorpay_order_id']:
        
            if razorpay_client.utility.verify_payment_signature({
                                                                'razorpay_order_id': data['razorpay_order_id'],
                                                                'razorpay_payment_id': data['razorpay_payment_id'],
                                                                'razorpay_signature': data['razorpay_signature']
                                                                }):
                #print("payment verified")
                cursor.execute('UPDATE order_generate SET razorpay_payment_id = %s, razorpay_signature = %s WHERE razorpay_order_id = %s', (data['razorpay_payment_id'], data['razorpay_signature'], data['razorpay_order_id']))
                connection.commit()
            else:  
                return jsonify({'error': 'Payment verification failed'})
        else:
            return jsonify({'error': 'order mismatched with last order'})

        cursor.execute("SELECT * FROM users WHERE cust_id = %s", (order['cust_id'],))
        customer = cursor.fetchone()

        #print("found the user object")
        # Re-authenticate user
        user = User(id=customer['cust_id'], username=customer['username'], password=customer['password'], role=customer['role'])
        if user:
            login_user(user)  # Restore Flask-Login session
        
        #print("logged in the user")
        #print(current_user.username)
              
        cursor.close()
        connection.close()
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("select email from addresses where user_id =%s",(order['cust_id'],))       
        email=cursor.fetchone()
        # send email to customer
        msg = Message(f'Nirviyu: Order Placed - {id}', sender='info@nirviyu.com', recipients=[email[0]])
        #msg.body = (f'Hi {current_user.username} \n\n You order has been placed. \n\n regards \n Team Nirivyu \n This is an auto generated email.Do not Reply.****')
        msg.html = render_template("email_template.html", name=current_user.username)
        mail.send(msg)
        
        # send email to admin
        msg = Message(f'Nirviyu: New Order Placed - {id}', sender='info@nirviyu.com', recipients=['mohanmurali.behera@gmail.com','tusharbpt@yahoo.in'])
        msg.body = (f'Hi Admin, \n\nNew order has been placed. \nReview the Order: {id} for fulfillment. \n\n regards \n Team Nirivyu \n ***This is an auto generated email.Do not Reply.***')
        mail.send(msg)
        return render_template('payment_success.html', data=data)
    except mysql.connector.Error as err:
        return jsonify({'Sql error': str(err)})
    except Exception as e:
        return jsonify({'exception error': str(e)})
    
@app.route('/webhook_nirviyu', methods=['POST'])
def webhook_nirviyu():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        data = request.get_json()
      
        #print(data)
        cursor.execute('SELECT * FROM order_generate WHERE razorpay_order_id = %s', (data['payload']['payment']['entity']['order_id'],))
        order = cursor.fetchone()
        if order:
            cursor.execute('UPDATE order_checkout SET payment_status = %s WHERE razorpay_order_id = %s', ("success", data['payload']['payment']['entity']['order_id']))
            connection.commit()
            
            #fetch the details of the order which you want to pass for shipment
            query='''select oc.order_id,oc.payment_status,oc.razorpay_order_id,oc.checkout,oc.total_qty,oc.length,oc.width,oc.height,oc.weight,og.amount,ad.* from order_checkout as oc inner join addresses as ad on oc.add_id=ad.add_id inner join order_generate as og on og.razorpay_order_id=oc.razorpay_order_id where oc.razorpay_order_id=%s and oc.payment_status="success"'''         
            cursor.execute(query,(data['payload']['payment']['entity']['order_id'],))
            order_info = cursor.fetchone()
            print("fetched the order_info")
            print(order_info)
            # get the order details
            
            order_details = {
            "order_id": str(order_info['order_id']),
            "order_date": order_info['checkout'].strftime("%Y-%m-%d"),
            "customer_name": order_info['full_name'],
            "billing_address": order_info['address_line1']+", "+order_info['address_line2'],
            "billing_city": order_info['city'],
            "billing_pincode": order_info['postal_code'],
            "billing_state": order_info['state'],
            "email": order_info['email'],
            "phone": order_info['phone'],
            "cod": False,
            "sub_total": float(order_info['amount']),
            "length": order_info['length'],
            "breadth": order_info['width'],
            "height": order_info['height'],
            "weight": float(order_info['weight'])
            }
       

        # Create order in Shiprocket
        shiprocket_response = create_shiprocket_order(order_details)
              
            
            
            
        cursor.close()
        connection.close()
        return jsonify({'status': 'success'})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/order_history', methods=['GET','POST'])
@login_required
def order_history():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("select  og.order_id, og.updated_at as order_date, oc.payment_status,cast(avg(og.amount) as decimal(20,2)) as amount, group_concat(p.prod_name separator ', ') as product_details,s.status as shipment_status from order_generate as og inner join orders as o on o.order_id = og.order_id inner join products as p on p.prod_id = o.prod_id inner join order_checkout as oc on oc.order_id = og.order_id inner join shipment as s on s.internal_order_id=og.order_id where o.cust_id = %s and oc.payment_status ='success' group by 1,2,3,6", (current_user.id,))
        orders = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('order_history.html', orders=orders)
    except Exception as e:
        return jsonify({'error': str(e)})


# Route for managing product deletion
@app.route('/admin/delete-product', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def delete_product():
    if request.method == 'POST':
        product_id = request.form.get('product_id')

        if product_id:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            
            # delete the images from static folder
            cursor.execute("SELECT image_url FROM product_images WHERE product_id = %s", (product_id,))
            product = cursor.fetchall()
            if product:
                for image_url in product:
                    [d,url]=image_url['image_url'].split("/", maxsplit=1)
                    if os.path.exists(url):
                        os.remove(url)
            cursor.execute("DELETE FROM products WHERE prod_id = %s", (product_id,))
            connection.commit()
            cursor.close()
            connection.close()


            flash("Product deleted successfully!", "success")
            return redirect(url_for('delete_product'))

    return render_template('remove_products.html')

# route for viewing products
@app.route('/admin/view-product', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def view_product():
    
    return render_template('view_product.html')

# AJAX search for products
@app.route('/search-products', methods=['GET'])
def search_products():
    query = request.args.get('query', '')
    #print(query)
    if query:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("SELECT a.*,b.image_url FROM products as a left join (select * from (select *, rank() over(partition by product_id order by id asc) as Rank_  from product_images) as a where a.Rank_=1) as b on a.prod_id=b.product_id")
        products = cursor.fetchall()  # Returns list of tuples (id, name)

        # Apply fuzzy matching
        product_names = [p[1] for p in products]
        matches = process.extract(query, product_names, limit=5, scorer=fuzz.partial_ratio, score_cutoff=60)

        # Get product IDs of the best matches
        results = [{"prod_id": products[product_names.index(match[0])][0],
                    "prod_name": match[0],
                    "description":products[product_names.index(match[0])][2],
                    "price":products[product_names.index(match[0])][3],
                    "path":products[product_names.index(match[0])][4],
                    "discount":products[product_names.index(match[0])][5],
                    "highlight1":products[product_names.index(match[0])][6],
                    "highlight2":products[product_names.index(match[0])][7],
                    "highlight3":products[product_names.index(match[0])][8],
                    "highlight4":products[product_names.index(match[0])][9],
                    "highlight5":products[product_names.index(match[0])][10],
                    "product_info":products[product_names.index(match[0])][11],
                    "ingredients":products[product_names.index(match[0])][12],
                    "allergens":products[product_names.index(match[0])][13],
                    "disclaimer":products[product_names.index(match[0])][14],
                    "sku":products[product_names.index(match[0])][15],
                    "image_url":products[product_names.index(match[0])][16]
                    
                    } for match in matches]
        #print(results)
        
        #connection = mysql.connector.connect(**db_config)
        #cursor = connection.cursor(dictionary=True)
        #cursor.execute("SELECT prod_id, prod_name, price FROM products WHERE prod_name LIKE %s LIMIT 10", (f"%{query}%",))
        #products = cursor.fetchall()
        #print(products)
        cursor.close()
        connection.close()

        return jsonify(results)

    return jsonify([])

# Route to add a new product
@app.route('/admin/add-product', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        discount = request.form.get('discount')
        category = request.form.get('category')
        highlight1=request.form.get('highlight1')
        highlight2=request.form.get('highlight2')
        highlight3=request.form.get('highlight3')
        highlight4=request.form.get('highlight4')
        highlight5=request.form.get('highlight5')
        #image = request.files.get('image')

        if not name or not price or not category:
            flash("All fields are required!", "error")
            return redirect(url_for('add_product'))

        # if image and allowed_file(image.filename):
        #     filename = secure_filename(image.filename)
        #     image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        #     image.save(image_path)  # Save image to the uploads folder
        # else:
        #     flash("Invalid image format! Please upload PNG, JPG, or JPEG.", "error")
        #     return redirect(url_for('add_product'))

        # Insert into database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("INSERT INTO products (prod_name, price, description, discount,highlight1,highlight2,highlight3,highlight4,highlight5) VALUES (%s, %s, %s, %s,%s,%s,%s,%s,%s)", (name, price, category,discount,highlight1,highlight2,highlight3,highlight4,highlight5))
                       
        connection.commit()
        cursor.close()
        connection.close()

        flash("Product added successfully!", "success")
        return redirect(url_for('add_product'))

    return render_template('add_products.html')



@app.route('/update_products')
@login_required
@roles_required('admin')
def update_products():
    return render_template('update_products.html')


@app.route('/update_product', methods=['POST'])
def update_product():
    product_id = request.form['product_id']
    name = request.form['product_name']
    description = request.form['description']
    price = request.form['price']
    discount = request.form['discount']
    highlight1=request.form['highlight1']
    highlight2=request.form['highlight2']
    highlight3=request.form['highlight3']
    highlight4=request.form['highlight4']
    highlight5=request.form['highlight5']
    product_info=request.form['product_info']
    ingredients=request.form['ingredients']
    allergens=request.form['allergens']
    disclaimer=request.form['disclaimer']
    sku=request.form['sku']
    
    

    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    cursor.execute("UPDATE products SET prod_name=%s, description =%s, price=%s, discount=%s, highlight1=%s, highlight2=%s, highlight3=%s, highlight4=%s, highlight5=%s,product_info=%s,ingredients=%s,allergens=%s,disclaimer=%s,sku=%s WHERE prod_id=%s",
                   (name, description, price, discount,highlight1,highlight2,highlight3,highlight4,highlight5,product_info,ingredients,allergens,disclaimer,sku, product_id))
    connection.commit()
    cursor.close()
    connection.close()
    flash("product Updated Successfully!",'success')

    return redirect(url_for('update_products'))


# confirm address
@app.route('/address', methods=['GET', 'POST'])
def address():
    # Ensure user is logged in
    if not current_user.username:
        flash("Please log in to place an order.", "warning")
        return redirect(url_for('login'))
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)    
    cursor.execute("SELECT * FROM addresses WHERE user_id = %s", (current_user.id,))
    addresses = cursor.fetchall()

    return render_template('address.html', addresses=addresses)


# upload photos
@app.route("/admin/upload-photos/<int:product_id>", methods=["GET", "POST"])
@login_required
@roles_required('admin')
def upload_photos(product_id):
    if request.method == "POST":
        files = [
            request.files.get(f"photo{i}") for i in range(1, 11)
            if request.files.get(f"photo{i}") and allowed_file(request.files.get(f"photo{i}").filename)
        ]

        if not files:
            flash("No valid files selected.", "error")
            return redirect(request.url)

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # Save file path in database
            cursor.execute(
                "INSERT INTO product_images (product_id, image_url) VALUES (%s, %s)",
                (product_id, f"../static/uploads/{filename}"),
            )

        connection.commit()
        cursor.close()
        connection.close()

        flash("Photos uploaded successfully", "success")
        return redirect(url_for("upload_photos", product_id=product_id))

    return render_template("upload_images.html", product_id=product_id)


@app.route('/enquiry', methods=['GET','POST'])
def enquiry():
    form=ContactForm()
    # if request.method == 'POST':
        
    if form.validate_on_submit():
        secret_response=request.form['g-recaptcha-response']
        #print(secret_response)
        
        verify_response = requests.post(url=f"{verify_url}?secret={RECAPTCHA_PRIVATE_KEY}&response={secret_response}").json()
        if not verify_response['success']:
            abort(400)
        else:
    
            # name = request.form.get('name')
            # email = request.form.get('email')
            # #phone = request.form.get('phone')
            # message = request.form.get('message')
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            cursor.execute("INSERT INTO enquiry (enquiry_name, enquiry_email, enquiry_content) VALUES (%s, %s, %s)", (form.name.data, form.email.data, form.message.data))
            connection.commit()
            cursor.close()
            connection.close()
            
        
            #send email to admin
            
            msg = Message(f'Nirviyu: New Enquiry ', sender='info@nirviyu.com', recipients=['mohanmurali.behera@gmail.com','tusharbpt@yahoo.in'])
            msg.body = (f'Hi \n\nNew Enquiry Received. \n\nName: {form.name.data}\nEmail: {form.email.data}\nQuery:{form.message.data}\n\nregards \nTeam Nirivyu \n***This is an auto generated email.Do not Reply.***')
            # msg.html = render_template("email_template.html", name=current_user.username)
            mail.send(msg)
            
            #send email to user
            msg = Message(f'Nirviyu: Enquiry Received',sender='info@nirviyu.com', recipients=[f'{form.email.data}'])
            msg.body = (f'Hi {form.name.data}, \n\nYour enquiry has been received.\n\nEnquiry: {form.message.data} \n\nregards \nTeam Nirivyu \n***This is an auto generated email.Do not Reply.****')
            mail.send(msg)
            flash('Enquiry Captured! Our team will get back to you.','success')
            return redirect(url_for('index',_anchor='know_more'))
    else:
        flash('Please enter the correct details','error')
        return redirect(url_for('index',_anchor='know_more'))
    return redirect(url_for('index'))

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@app.route('/dashboard')
@login_required
@roles_required('admin')
def dashboard():
    return render_template('dashboard.html')

@app.route('/dashboard-data')
def dashboard_data():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # Orders per day
    cursor.execute("SELECT DATE_FORMAT(created_at, '%d-%b') AS order_day, COUNT(*) AS total_orders FROM orders GROUP BY order_day ORDER BY order_day desc limit 10")
    orders_per_day = cursor.fetchall()
    #print(orders_per_day)

    # Orders per shipment status
    cursor.execute("SELECT DATE_FORMAT(o.checkout,'%d-%b') AS order_day, s.status, COUNT(*) AS count FROM order_checkout o JOIN shipment s ON o.order_id = s.internal_order_id GROUP BY order_day, s.status ORDER BY order_day")
    orders_by_status = cursor.fetchall()

    # Top-selling products
    cursor.execute("SELECT p.prod_id as product_name, SUM(o.qty) AS total_sold FROM orders o JOIN products p ON o.prod_id = p.prod_id GROUP BY product_name ORDER BY total_sold DESC LIMIT 10")
    top_products = cursor.fetchall()

    # Summary metrics
    cursor.execute("SELECT COUNT(*) AS total_orders_today FROM order_checkout WHERE DATE(checkout) = CURDATE() and payment_status='success'")
    total_orders_today = cursor.fetchone()['total_orders_today']

    cursor.execute("SELECT COUNT(*) AS total_shipped FROM shipment WHERE status LIKE '%PICK%'")
    total_shipped = cursor.fetchone()['total_shipped']

    cursor.execute("SELECT COUNT(*) AS pending_shipments FROM shipment WHERE status = 'NEW'")
    pending_shipments = cursor.fetchone()['pending_shipments']

    cursor.execute("SELECT coalesce(SUM(subtotal),0) AS revenue FROM orders where DATE(created_at) = CURDATE()")
    revenue = cursor.fetchone()['revenue']

    conn.close()
    
    return jsonify({
        "orders_per_day": orders_per_day,
        "orders_by_status": orders_by_status,
        "top_products": top_products,
        "summary": {
            "total_orders_today": total_orders_today,
            "total_shipped": total_shipped,
            "pending_shipments": pending_shipments,
            "revenue": revenue
        }
    })


@app.route('/lab_tests')
def lab_tests():
    return render_template('lab_tests.html')

@app.route('/get_lab_products', methods=['GET'])
def get_products():
    provider = request.args.get('provider', '')
    query = request.args.get('query', '').lower()
    connection=mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)

    if not provider or not query:
        return jsonify([])

    sql = """
        SELECT tc_prod_name FROM thyrocare_tests
        WHERE LOWER(tc_prod_name) LIKE %s
        LIMIT 10
    """
    cursor.execute(sql, (f"%{query}%",))
    result = cursor.fetchall()
    
    connection.close()
    cursor.close()

    # Extract product names only
    suggestions = [row['tc_prod_name'] for row in result]
    return jsonify(suggestions)

@app.route('/search_lab_details', methods=['POST'])
def search_details():
    provider = request.form.get('provider')
    product = request.form.get('product')
    
    connection=mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)

    if not provider or not product:
        return jsonify({'error': 'Provider and Product are required'}), 400

    sql = """
        SELECT * FROM thyrocare_tests
        WHERE tc_prod_name = %s
        LIMIT 1
    """
    cursor.execute(sql, (product,))
    result = cursor.fetchone()

    if not result:
        return jsonify({'error': 'No product found'}), 404

    return jsonify(result)

@app.route('/book_lab_test', methods=['POST'])
def book_now():
    provider = request.form.get('provider')
    product = request.form.get('product')

    # Optional: Validate and check if already booked
    # sql = "INSERT INTO bookings (provider_name, product_name) VALUES (%s, %s)"
    # cursor.execute(sql, (provider, product))
    # db.commit()

    return jsonify({'message': 'Booking successful!'})


@app.route('/pincode_check_thyrocare', methods=['POST'])
def pincode_check():
    pincode = request.form.get('pincode')
    
    response = check_pincode_availability_thyrocare(pincode)
    print(response)
    if response['response'] == 'Success':
        result = {
            'serviceable': True,
            'message': f'Pincode {pincode} is serviceable',
        }
    else:
        result = {
            'serviceable': False,
            'message': 'pincode is not serviceable'
        }
    return jsonify(result)

if __name__ == '__main__':
    app.run(host=os.getenv('host'),port=int(os.getenv('port')),debug=os.getenv('DEBUG'))  # run the Flask app in debug mode
    