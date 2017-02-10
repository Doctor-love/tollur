#!/usr/bin/env python3

import smtplib

sender = 'u1@t1.example.com'
receivers = ['u2@t1.example.com', 'u3@t2.example.com']

message = '''From: Test Testsson <u1@t1.example.com>
To: Example Exampleberg <u2@t1.example.com>
Subject: Testing...

This is a test message
'''

try:
   smtpObj = smtplib.SMTP('127.0.0.1', 9025)
   smtpObj.sendmail(sender, receivers, message)         
   print('Successfully sent email')

except Exception as error_msg:
   print('Error: unable to send email: %s' % error_msg)
