# -*- coding: utf-8 -*-
from django.conf import settings

from ipalib import api, errors as ipaerrors
import redis
import re
import subprocess
#import os
#import requests
from random import SystemRandom
from datetime import datetime, timedelta
import sys
#from python_freeipa.exceptions import *
from password_strength import PasswordPolicy

if sys.version_info.major == 3:
    unicode = str

class TooMuchRetries(Exception):
    pass

class ValidateUserFailed(Exception):
    pass

class BackendError(Exception):
    pass

class InvalidToken(Exception):
    pass

class InvalidProvider(Exception):
    pass

class SetPasswordFailed(Exception):
    pass

class KerberosInitFailed(Exception):
    pass

class PasswdManager():
    def __init__(self):
        if self.__kerberos_has_ticket() is False:
            self.__kerberos_init()
        if api.isdone('finalize') is False:
            api.bootstrap_with_global_options(context='api')
            api.finalize()
        api.Backend.rpcclient.connect()
        self.redis = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD)
#        self.current_host = os.uname()[1]
#        self._session = requests.Session()
        
    
    @staticmethod
    def __kerberos_has_ticket():
        process = subprocess.Popen(['/usr/bin/klist', '-s'], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        process.communicate()
        if process.returncode == 0:
            return True
        else:
            return False
    
    @staticmethod
    def __kerberos_init():
        process = subprocess.Popen(['/usr/bin/kinit', '-k', '-t', str(settings.KEYTAB_PATH), str(settings.LDAP_USER), ], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        process.communicate()
        if process.returncode != 0:
            raise  KerberosInitFailed("Cannot retrieve kerberos ticket.")
######## Change Password using the url ###########
#    def __change_password(self, uid, old_password, new_password, otp=None):
#        """
#        private function, use change_password instead
#        """
#        password_url = 'https://{0}/ipa/session/change_password'.format(self.current_host)
#        headers = {
#            'Content-Type': 'application/x-www-form-urlencoded',
#            'Accept': 'text/plain',
#        }
#
#        data = {
#            'user': uid,
#            'new_password': new_password,
#            'old_password': old_password,
#        }
#        if otp:
#            data['otp'] = otp
#        response = self._session.post(
#            password_url, headers=headers, data=data, verify=True
#        )
#
#        if not response.ok:
#            raise FreeIPAError(message=response.text, code=response.status_code)
#
#        pwchange_result = response.headers.get('X-IPA-Pwchange-Result', None)
#        if pwchange_result != 'ok':
#            if pwchange_result == 'invalid-password':
#                raise SetPasswordFailed("Cannot update your password. You have entered {0}".format(pwchange_result))
#            elif pwchange_result == 'policy-error':
#                policy_error = response.headers.get('X-IPA-Pwchange-Policy-Error', None)
#                raise SetPasswordFailed("Cannot update your password. {0}".format(policy_error))
#            else:
#                raise FreeIPAError(message=response.text, code=response.status_code)
#        return response
#
#######################################################   

############### Validate Password Policy #####################
    def __vaidate_password(self, new_password):
        policy = PasswordPolicy.from_names(
            length=8,  # min length: 8
            uppercase=2,  # need min. 2 uppercase letters
            numbers=2,  # need min. 2 digits
            special=1,  # need min. 2 special characters
            nonletters=0,  # need min. 2 non-letter characters (digits, specials, anything)
        )
        
        validate = policy.test(new_password)
        if validate:
            raise SetPasswordFailed("Cannot update your password. Your password should have atleast {0}".format(validate))
        
##############################################################
    def __set_password(self, uid, password):
        try:
            api.Command.user_mod(uid=unicode(uid), userpassword=unicode(password))
            password_exp_days = int(api.Command.pwpolicy_show()['result']['krbmaxpwdlife'][0])
            if password_exp_days > 0:
                date = (datetime.now() + timedelta(days=password_exp_days)).strftime("%Y%m%d%H%M%SZ")
                api.Command.user_mod(uid=unicode(uid), setattr=unicode("krbPasswordExpiration={0}".format(date)))
            user = self.__get_user(uid)
            if 'krbloginfailedcount' in user['result'] and int(user['result']['krbloginfailedcount'][0]) > 0:
                api.Command.user_mod(uid=unicode(uid), setattr=unicode("krbloginfailedcount=0"))
        except Exception as e:
            raise SetPasswordFailed("Cannot update your password. {0}".format(e))
                    
    def __get_user(self, uid):
        try:
            user = api.Command.user_show(uid=unicode(uid), all=True)
        except ipaerrors.NotFound:
            raise ValidateUserFailed("User not found")
        except Exception:
            raise BackendError("Cannot fetch user information")
        if user['result']['nsaccountlock'] is True:
            raise ValidateUserFailed("Account is deactivated")
        return user
    
    def __gen_secure_token(self, length):
        token = int(''.join([ str(SystemRandom().randrange(9)) for i in range(length) ]))
        return token
        
    def __set_token(self, uid):
        if (self.redis.get("retry::send::{0}".format(uid)) is not None) and (int(self.redis.get("retry::send::{0}".format(uid))) >= settings.LIMIT_MAX_SEND):
            raise TooMuchRetries("Too many retries. Try later.")
        self.redis.incr("retry::send::{0}".format(uid))
        self.redis.expire("retry::send::{0}".format(uid), settings.LIMIT_TIME)
        token = self.__gen_secure_token(settings.TOKEN_LEN)
        self.redis.set("token::{0}".format(uid), token)
        self.redis.expire("token::{0}".format(uid), settings.TOKEN_LIFETIME)
        return token
    
    def __validate_token(self, uid, token):
        if (self.redis.get("retry::validate::{0}".format(uid)) is not None) and (int(self.redis.get("retry::validate::{0}".format(uid))) >= settings.LIMIT_MAX_VALIDATE_RETRY):
            raise TooMuchRetries("Too many retries. Try later.")
        server_token = self.redis.get("token::{0}".format(uid))
        if (server_token is not None) and (int(token) == int(server_token)):
            return True
        else:
            self.redis.incr("retry::validate::{0}".format(uid))
            self.redis.expire("retry::validate::{0}".format(uid), settings.TOKEN_LIFETIME)
            raise InvalidToken("You entered an incorrect code")
    
    def __invalidate_token(self, uid):
        self.redis.delete("token::{0}".format(uid))
        self.redis.delete("retry::send::{0}".format(uid))
        self.redis.delete("retry::validate::{0}".format(uid))

    def first_phase(self, uid, provider_id):
        user = self.__get_user(uid)
        token = self.__set_token(uid)

        if (provider_id not in settings.PROVIDERS):
            raise InvalidProvider("Specified provider does not exist")
        elif ("enabled" not in settings.PROVIDERS[provider_id]) or (settings.PROVIDERS[provider_id]['enabled'] is False):
            raise InvalidProvider("Specified provider disabled")
        else:
            provider = settings.PROVIDERS[provider_id]['class'](settings.PROVIDERS[provider_id]['options'])
            
        try:
            provider.send_token(user, token)
        except Exception as e:
            self.__invalidate_token(uid)
            raise e
        
    def second_phase(self, uid, token, new_password):
        self.__validate_token(uid, token)
        self.__vaidate_password(new_password)
        self.__set_password(uid, new_password)
#        self.__change_password(uid, old_password, new_password)
        self.__invalidate_token(uid)
        
def get_providers():
    providers = []
    for key, value in settings.PROVIDERS.items():
        if ('enabled' in value) and (value['enabled']):
            providers.append({"id": key, "display_name": value['display_name']})
    return providers



