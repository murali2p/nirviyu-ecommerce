import razorpay

#razorpay payment gateway configuration
RAZORPAY_KEY_ID ="rzp_test_JxBtA5Uv71LgLO"
RAZORPAY_KEY_SECRET ="OXGcRV5G9t5kkoMFwskVjui2"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# data = { "amount": 500, "currency": "INR", "receipt": "order_rcptid_11" }
# payment = razorpay_client.order.create(data=data)



result = razorpay_client.utility.verify_payment_signature({
  'razorpay_order_id': 'order_Q1wkBftxOVhiHf',
  'razorpay_payment_id': 'pay_Q1wkKUTags4zTD',
  'razorpay_signature': '475c0e3de77ccfe245642aa2d68842dabcea014254aba330b90df9c896b02dc7'
  })

print(result)