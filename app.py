from flask import Flask, request, jsonify, render_template,session,redirect,url_for,abort,flash
from flask_login import login_user, LoginManager, login_required, UserMixin, logout_user, current_user
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError,Email
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import razorpay
from datetime import timedelta
import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)  # create a new Flask app
app.secret_key = 'your_secret_key' 
# Set a longer session lifetime (e.g., 30 minutes)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
# upload config
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Check if uploaded file is an image
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#razorpay payment gateway configuration
RAZORPAY_KEY_ID ="rzp_test_JxBtA5Uv71LgLO"
RAZORPAY_KEY_SECRET ="OXGcRV5G9t5kkoMFwskVjui2"
RAZORPAY_WEBHOOK_SECRET = "Maruti@123"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

data = { "amount": 500, "currency": "INR", "receipt": "order_rcptid_11" }
payment = razorpay_client.order.create(data=data)



# SQl Database Configuration #
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'murali123',
    'database': 'nirviyu',
    'auth_plugin': 'mysql_native_password'
}


# email configuration

app.config['MAIL_SERVER'] = 'smtpout.secureserver.net'
app.config['MAIL_PORT'] = 465  # For TLS
# Alternatively, you can use port 465 for SSL
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'info@nirviyu.com'
app.config['MAIL_PASSWORD'] = 'Payal@1989'
recipients = ['mohanmurali.behera@gmail.com']

#initialize the Mail

mail = Mail(app)


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
            msg = Message('User Logged in', sender='info@nirviyu.com', recipients=recipients)
            msg.body = (f'Hi, \n\n User  {current_user.username} has logged. \n This is an auto generated email.Do not Reply.****')
            mail.send(msg)
            if current_user.role == 'admin':
                return redirect(url_for('index_admin'))
            else:
                return redirect(url_for('index'))
        else:
            return 'user_not_found'
    return render_template('login.html', form=form)

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

    return render_template('index.html')

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
        cursor.execute('SELECT * FROM products')
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
        # execute the SQL query
        cursor.execute('SELECT * FROM products WHERE prod_id = %s', (id,))
        # fetch the result
        result = cursor.fetchone()
        # close the cursor and the connection
        cursor.close()
        connection.close()
        # return the response
        return render_template('product_details.html', product=result)
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
        cursor.execute('UPDATE cart SET subtotal = qty * price WHERE cust_id = %s and prod_id =%s', (current_user.id,product['prod_id']))
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
    cursor.execute('SELECT * FROM cart inner join products on cart.prod_id =products.prod_id WHERE cart.cust_id = %s', (current_user.id,))
    cart = cursor.fetchall()
    print(cart)
    cursor.close()
    connection.close()
    total_amt = 0
    for item in cart:
        total_amt+=item['subtotal']

    return render_template('cart.html', cart=cart, total_amt=total_amt)
 

@app.route('/add_to_order', methods=['POST'])
@login_required
def add_to_order():
   # caculate the total amount
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM cart inner join products on cart.prod_id =products.prod_id WHERE cart.cust_id = %s', (current_user.id,))
        cart = cursor.fetchall()
        print(cart)
        total_amt = 0
        for item in cart:
            total_amt+=item['subtotal']
        
        print(total_amt)
    
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
        print(order_id)
        
        # insert the order_id into the order_checkout table
        query = "INSERT INTO order_checkout (order_id,razorpay_order_id, cust_id, checkout) VALUES (%s, %s,%s, %s)"
        cursor.execute(query, (order_id['order_id'],payment['id'], current_user.id, current_time))
        
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
        print("the order is placed")
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
        
        return render_template('orders.html',order_id=order_id['order_id'], orders=orders, payment=payment)
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
        print(order['razorpay_order_id'])
        print(data['razorpay_order_id'])
        
        if order['razorpay_order_id'] == data['razorpay_order_id']:
        
            if razorpay_client.utility.verify_payment_signature({
                                                                'razorpay_order_id': data['razorpay_order_id'],
                                                                'razorpay_payment_id': data['razorpay_payment_id'],
                                                                'razorpay_signature': data['razorpay_signature']
                                                                }):
                print("payment verified")
                cursor.execute('UPDATE order_generate SET razorpay_payment_id = %s, razorpay_signature = %s WHERE razorpay_order_id = %s', (data['razorpay_payment_id'], data['razorpay_signature'], data['razorpay_order_id']))
                connection.commit()
            else:  
                return jsonify({'error': 'Payment verification failed'})
        else:
            return jsonify({'error': 'order mismatched with last order'})

        cursor.execute("SELECT * FROM users WHERE cust_id = %s", (order['cust_id'],))
        customer = cursor.fetchone()

        print("found the user object")
        # Re-authenticate user
        user = User(id=customer['cust_id'], username=customer['username'], password=customer['password'], role=customer['role'])
        if user:
            login_user(user)  # Restore Flask-Login session
        
        print("logged in the user")
        print(current_user.username)
              
        cursor.close()
        connection.close()
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
        cursor.execute("select  og.order_id, og.updated_at as order_date, oc.payment_status,cast(avg(og.amount) as decimal(20,2)) as amount, group_concat(p.prod_name separator ', ') as product_details from order_generate as og inner join orders as o on o.order_id = og.order_id inner join products as p on p.prod_id = o.prod_id inner join order_checkout as oc on oc.order_id = og.order_id where o.cust_id = %s and oc.payment_status ='success' group by 1,2,3", (current_user.id,))
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
            
            cursor.execute("SELECT path FROM products WHERE prod_id = %s", (product_id,))
            product = cursor.fetchone()
            if product:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['path'])
                if os.path.exists(image_path):
                    os.remove(image_path)
            cursor.execute("DELETE FROM products WHERE prod_id = %s", (product_id,))
            connection.commit()
            cursor.close()
            connection.close()

            flash("Product deleted successfully!", "success")
            return redirect(url_for('delete_product'))

    return render_template('remove_products.html')

# AJAX search for products
@app.route('/search-products', methods=['GET'])
def search_products():
    query = request.args.get('query', '')
    print(query)
    if query:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT prod_id, prod_name, price FROM products WHERE prod_name LIKE %s LIMIT 10", (f"%{query}%",))
        products = cursor.fetchall()
        print(products)
        cursor.close()
        connection.close()

        return jsonify(products)

    return jsonify([])

# Route to add a new product
@app.route('/admin/add-product', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category')
        image = request.files.get('image')

        if not name or not price or not category:
            flash("All fields are required!", "error")
            return redirect(url_for('add_product'))

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)  # Save image to the uploads folder
        else:
            flash("Invalid image format! Please upload PNG, JPG, or JPEG.", "error")
            return redirect(url_for('add_product'))

        # Insert into database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("INSERT INTO products (prod_name, price, description, path) VALUES (%s, %s, %s, %s)",
                       (name, price, category, filename))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Product added successfully!", "success")
        return redirect(url_for('add_product'))

    return render_template('add_products.html')


if __name__ == '__main__':
    app.run(debug=True)  # run the Flask app in debug mode
    