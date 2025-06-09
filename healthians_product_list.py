
file_name=r"C:\Users\mohan\Documents\Goel_Insurance_project\website_pharma\Healthy India 2025 Full Body Checkup With Hormone_package_5071.csv"

with open(file_name, 'r', encoding='utf-8') as file:
    lines = file.readlines()
    lines = [line.split(',') for line in lines if line.strip()] 
    # Remove empty lines and strip whitespace
    products = []
    for line in lines[1:]:  # Skip the header line
        product = {
            'code': line[0].strip(),
            'name': line[1].strip()+' ' + line[2].strip(),
            'groupname': line[3].strip(),
            'type': 'null'

        }
        products.append(product)
    # Create a list of dictionaries for each product
    print(products)