import boto3
import re
import smtplib
from email.mime.text import MIMEText

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class AmazonSNSFailed(Exception):
    pass

class AmazonSNSValidateFailed(Exception):
    pass

class EmailSendFailed(Exception):
    pass

class EmailValidateFailed(Exception):
    pass

class AmazonSNS():
    def __init__(self, options):
        self.msg_template = options['msg_template']
        self.aws_key = options['aws_key']
        self.aws_secret = options['aws_secret']
        self.aws_region = options['aws_region']
        self.sender_id = options['sender_id']

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
        phones = user['result']['telephonenumber']
        phones = self.__filter_phones(phones)
        
        try:
            sns = boto3.client('sns', aws_access_key_id=self.aws_key, aws_secret_access_key=self.aws_secret, region_name=self.aws_region)
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
            msg['From'] = self.smtp_user
            msg['To'] = ", ".join(recipients)
            s = smtplib.SMTP("{0}:{1}".format(self.smtp_server_addr, self.smtp_server_port))
            if self.smtp_server_tls:
                s.ehlo()
                s.starttls(tuple())
                s.ehlo()
            if (self.smtp_user is not None) and (self.smtp_pass is not None:
                s.login(self.smtp_user, self.smtp_pass)
            s.sendmail(msg['From'], recipients, msg.as_string())
            s.quit()
        except Exception:
            raise EmailSendFailed("Cannot send Email")