import razorpay

#razorpay payment gateway configuration
RAZORPAY_KEY_ID ="rzp_test_JxBtA5Uv71LgLO"
RAZORPAY_KEY_SECRET ="OXGcRV5G9t5kkoMFwskVjui2"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

data = { "amount": 500, "currency": "INR", "receipt": "order_rcptid_11" }
payment = razorpay_client.order.create(data=data)

print(payment)