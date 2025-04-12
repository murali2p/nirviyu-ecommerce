# Thanks for sharing the API key format! Here are a few things to check when passing the key in your request:
# - URL Encoding
# Since your API key contains special characters like @, ), and =, ensure it's properly URL-encoded if needed. You can encode it using Python’s urllib.parse:
import urllib.parse

B2CAPIKEY = "2oVtJaTDWS1uzn2Yv58@7s8m1)OO5L3BAomi@RBhXRrVcGyko7hIzQ=="
encoded_key = urllib.parse.quote(B2CAPIKEY, safe='')

print(encoded_key)

