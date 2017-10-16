# FreeIPA self-service password reset

## Features
1. Users can reset their own passwords with token that is sent to the user's mobile phone
2. The service has protection against brute force attacks
3. The service is dedicated. It does not change the scheme or system files of FreeIPA. No problems with upgrade of FreeIPA
4. The password reset page stylized as FreeIPA pages
5. SMS with tokens is sent through the Amazon SNS service. 
6. Tested with CentOS 7, python 2.7 and FreeIPA 4.4/4.5
7. This instruction assumes that the service will be installed on the FreeIPA server, but you can install it on another server
8. I recommend that you protect the service using a firewall and allow access only through the internal network
9. This app is very small. You can easily audit the code.


## Instal steps

1. Configure FreeIPA
2. Install & Configure App
3. Set users mobile phones in their profile. The service require phone in "Telephone Number" field in international format like '+79991234567'
4. Enjoy!

## Configure FreeIPA
1. Create service user (example: `ldap-passwd-reset`)
```
ipa -n user-add "ldap-passwd-reset" --first="Service" --last="Password reset" --password "CHANGE_ME_PLEASE"
```
2. Create new role with permission to change passwords
```
ipa role-add "Self Password Reset"
ipa role-add-member "Self Password Reset" --users="ldap-passwd-reset"
ipa role-add-privilege "Self Password Reset" --privileges="Modify Users and Reset passwords"
ipa role-add-privilege "Self Password Reset" --privileges="Password Policy Readers"
```



## Install App
1. Clone repository to directory. (default is `/opt/data/IPAPasswordReset/`, but you can change it.):
```
git clone https://github.com/larrabee/freeipa-password-reset.git /opt/data/IPAPasswordReset/
```
2. Create virtual env:
```
cd /opt/data/IPAPasswordReset/
virtualenv2 ./virtualenv
. ./virtualenv/bin/activate
pip install -r requirements.txt
```
3. Get keytab for "ldap-passwd-reset" user (you must run it from user with admin privileges):
```
ipa-getkeytab -p ldap-passwd-reset -k /opt/data/IPAPasswordReset/ldap-passwd-reset.keytab
```
4. chown files (change username if you use not default):
```
chown -R ldap-passwd-reset:ldap-passwd-reset /opt/data/IPAPasswordReset
```
5. Install Apache config and reload httpd:
```
cp service/ipa-password-reset.conf /etc/httpd/conf.d/ipa-password-reset.conf
systemctl reload httpd
```
6. Install redis (you can skip this step and use external redis):
```
yum install -y redis
systemctl enable --now redis
```
7. Change vars in `PasswordReset/PasswordReset/settings.py`. You need change following keys:
```
SECRET_KEY = "Your CSRF protection key. It must be long random string"
AWS_KEY = "Your AWS SNS key"
AWS_SECRET = "Your AWS SNS secret"
AWS_REGION = "Your AWS region"
LDAP_USER = "LDAP user. Default is ldap-passwd-reset"
KEYTAB_PATH = "Path to ldap-passwd-reset keytab. Default is ../ldap-passwd-reset.keytab"
```
8. Install systemd unit and start the app:
```
cp service/ldap-passwd-reset.service /etc/systemd/system/ldap-passwd-reset.service
systemctl daemon-reload
systemctl enable --now ldap-passwd-reset.service
```

## Enjoy!
* Open [https:/ipa.example.com/reset/](https://ipa.example.com/reset/) (replace ipa.example.com with your FreeIPA hosname)
* Enter the user uid and click 'Reset Password'
* On next page enter the security code from SMS and enter new password twice and click 'Reset'
* Try to login to FreeIPA with new password

## Screenshots
![Main Page](/service/main.png?raw=true "Main Page")
![Confirmation Page](/service/reset.png?raw=true "Confirmation Page")
