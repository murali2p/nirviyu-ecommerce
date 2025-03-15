from flask import Flask, request, render_template, jsonify
import mysql.connector
from rapidfuzz import process,fuzz

db_config={
'host':'localhost',
'user':'root',
'password':'murali123',
'database':'nirviyu',
'auth_plugin':'mysql_native_password'
}



# MySQL Connection
connection = mysql.connector.connect(**db_config)
cursor = connection.cursor()



    # Fetch product names from the database
cursor.execute("SELECT prod_id, prod_name FROM products")
products = cursor.fetchall()  # Returns list of tuples (id, name)

    # Apply fuzzy matching
product_names = [p[1] for p in products]
matches = process.extract('vimin', product_names, limit=5, scorer=fuzz.partial_ratio, score_cutoff=60)

    # Get product IDs of the best matches
results = [{"prod_id": products[product_names.index(match[0])][0], "prod_name": match[0]} for match in matches]

print(results)
    #return jsonify(results)


