import boto3
import re
import smtplib
import subprocess 
from email.mime.text import MIMEText

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

import json
import requests

class AmazonSNSFailed(Exception):
    pass

class AmazonSNSValidateFailed(Exception):
    pass

class EmailSendFailed(Exception):
    pass

class EmailValidateFailed(Exception):
    pass

class SignalFailed(Exception):
    pass

class SignalValidateFailed(Exception):
    pass

class SlackValidateFailed(Exception):
    pass

class SlackSendFailed(Exception):
    pass

class AmazonSNS():
    def __init__(self, options):
        self.msg_template = options['msg_template']
        self.aws_key = options['aws_key']
        self.aws_secret = options['aws_secret']
        self.aws_region = options['aws_region']
        self.sender_id = options['sender_id']
        if 'ldap_attribute_name' in options:
            self.ldap_attribute_name = options['ldap_attribute_name']
        else:
            self.ldap_attribute_name = 'telephonenumber'

    def __filter_phones(self, phones):
        phone_regexp = re.compile('^\+([\d]{9,15})$')
        valid_phones = []
        if len(phones) == 0:
            raise AmazonSNSValidateFailed("User does not have phone numbers")
        for phone in phones:
            if phone_regexp.match(phone) is not None:
                valid_phones.append(phone)
        if len(valid_phones) == 0:
            raise AmazonSNSValidateFailed("User does not have valid phone numbers")
        return valid_phones

    def send_token(self, user, token):
        phones = user['result'][self.ldap_attribute_name]
        phones = self.__filter_phones(phones)

        try:
            sns = boto3.client('sns', region_name=self.aws_region)
            for phone in phones:
                sns.publish(PhoneNumber=phone, Message=self.msg_template.format(token), MessageAttributes={'AWS.SNS.SMS.SenderID': {'DataType': 'String', 'StringValue': self.sender_id}})
        except Exception:
            raise AmazonSNSFailed("Cannot send SMS via Amazon SNS")



class Email():
    def __init__(self, options):
        self.msg_template = options['msg_template']
        self.msg_subject = options['msg_subject']
        self.smtp_user = options['smtp_user']
        self.smtp_pass = options['smtp_pass']
        self.smtp_server_addr = options['smtp_server_addr']
        self.smtp_server_port = options['smtp_server_port']
        self.smtp_server_tls = options['smtp_server_tls']
        if ('smtp_from' in options) and (options['smtp_from'] is not None):
            self.smtp_from = options['smtp_from']
        else:
            self.smtp_from = self.smtp_user

    def __filter_emails(self, emails):
        if len(emails) == 0:
            raise EmailValidateFailed("User does not have email addresses")
        filtered_emails = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                pass
            else:
                filtered_emails.append(email)
        if len(filtered_emails) == 0:
            raise EmailValidateFailed("User does not have valid email addresses")
        return filtered_emails

    def send_token(self, user, token):
        recipients = user['result']['mail']
        recipients = self.__filter_emails(recipients)

        try:
            msg = MIMEText(self.msg_template.format(token))
            msg['Subject'] = self.msg_subject
            msg['From'] = self.smtp_from
            msg['To'] = ", ".join(recipients)
            s = smtplib.SMTP("{0}:{1}".format(self.smtp_server_addr, self.smtp_server_port))
            if self.smtp_server_tls:
                s.ehlo()
                s.starttls(tuple())
                s.ehlo()
            if (self.smtp_user is not None) and (self.smtp_pass is not None):
                s.login(self.smtp_user, self.smtp_pass)
            s.sendmail(msg['From'], recipients, msg.as_string())
            s.quit()
        except Exception as e:
            raise EmailSendFailed("Cannot send Email, error: {0}".format(str(e)))

class Signal():
    def __init__(self, options):
        self.msg_template = options['msg_template']
        self.sender_number = options['sender_number']
        if 'ldap_attribute_name' in options:
            self.ldap_attribute_name = options['ldap_attribute_name']
        else:
            self.ldap_attribute_name = 'telephonenumber'

    def __filter_phones(self, phones):
        phone_regexp = re.compile('^\+([\d]{9,15})$')
        valid_phones = []
        if len(phones) == 0:
            raise SignalValidateFailed("User does not have phone numbers")
        for phone in phones:
            if phone_regexp.match(phone) is not None:
                valid_phones.append(phone)
        if len(valid_phones) == 0:
            raise SignalValidateFailed("User does not have valid phone numbers")
        return valid_phones

    def send_token(self, user, token):
        phones = user['result'][self.ldap_attribute_name]
        phones = self.__filter_phones(phones)
        try:
            for phone in phones:
                proc = subprocess.Popen(["signal-cli", "-u", self.sender_number, "send", "-m", self.msg_template.format(token), phone.encode('utf-8')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output = proc.communicate()[0]
                if proc.returncode != 0:
                    raise SignalFailed(output)
        except Exception as e:
            raise SignalFailed(e.message)

class Slack():
    def __init__(self, options):
        self.msg_template = options['msg_template']
        self.slack_hook = options['slack_hook']
        self.slack_username = options['slack_username']
        self.slack_icon_emoji = options['slack_icon_emoji']

    def __filter_login(self, uid):
        if len(uid) == 0:
            raise SlackValidateFailed("User login not found")
        return uid

    def send_token(self, user, token):
        recipient = user['result']['uid'][0]
        recipient = self.__filter_login(recipient)
        msg = self.msg_template.format(token)
        self.slack_payload = {'channel': '@%s' % recipient, 'username': self.slack_username, 'text': msg, 'icon_emoji': self.slack_icon_emoji, 'mrkdwn': 'true' }

        response = requests.post(
            self.slack_hook, data=json.dumps(self.slack_payload),
            headers={'Content-Type': 'application/json'}
        )
        print (response.status_code)

        if response.status_code != 200:
            raise SlackSendFailed(
                'Request to slack returned an error %s, the response is:\n%s'
                % (response.status_code, response.text)
            )
