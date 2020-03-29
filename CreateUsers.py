#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# CreateUsers.py v. 2.0
#
# Date 29.3.2020

# Import modules
import sys
import json
import logging
import requests
from bs4 import BeautifulSoup
import pandas as pd
import msal
import argparse
from datetime import datetime
import time
import re
import mysql.connector
import random
import string
from mysql.connector import errorcode
global error_msg
global error_level
global startTime
global arguments


parser = argparse.ArgumentParser(description='This Python script is used to export users from HAKA - Turvallisuusosaamisen hallinnointikanta and import them to Azure Active Directory.')
parser.add_argument('-c', '--config', help='Parameters.json file containing credentials.', required=True)
parser.add_argument('-v', '--verbose', help="Run verbosely. Print only on errors and when users modified.", action='store_true')
parser.add_argument('-d', '--debug', help="Run in debug mode. Print me everything, EVERYTHING!", action='store_true')
arguments = parser.parse_args()

startTime = datetime.now()
s=requests.Session()
soup = BeautifulSoup(s.get('https://haka.spek.fi/kirjaudu.aspx').text, features="lxml")
error_msg= []
error_level=0


def init(config):
    if (arguments.debug): print("\n\r"+"Connecting to SQL-server.")
    db_function = "connect"
    debug_result=(db_manager(db_function, config))
    if (arguments.debug): print(debug_result)
    if (debug_result.startswith('Error: ')):
        sys.exit(debug_result)

    if (arguments.debug): print("\n\r"+"Connecting to HAKA.")
    haka_function = "login"
    debug_result=(haka_connector(config, haka_function))
    if (arguments.debug): print(debug_result)

    if (arguments.debug): print("\n\r"+"Connecting to Azure Active Direcory.")
    aad_function = "login"
    debug_result=(aad_connector(config, aad_function))
    if (arguments.debug): print(debug_result)

def passwordGen(stringLength=10):
    characters = string.ascii_letters + string.digits * 2
    return ''.join(random.choice(characters) for i in range(stringLength))

def countdown(t):
    while t != 0:
        if (arguments.debug): print("Waiting for "+str(t)+" seconds.", end='\r')
        time.sleep(10)
        t-=10

    return

def cleanup(config):
    if (arguments.debug): print("\n\r"+"Starting cleanup() function.")

    aad_function = "aad_remove_groups"
    aad_connector(config, aad_function)

    aad_function = "aad_delete_users"
    aad_connector(config, aad_function)

    db_function = "cleanup"
    db_manager(db_function,config)


def haka_get_users(config):
    if (arguments.debug): print("\n\r"+"Starting haka_get_users() function.")
    haka_function = "haka_get_users"
    haka_connector(config, haka_function)


def haka_get_groups(config):
    if (arguments.debug): print("\n\r"+"Starting haka_get_groups() function.")
    haka_function = "haka_groups"
    haka_connector(config,haka_function)



def db_manager(db_function, config, param1="None", param2="None", param3="None", param4="None", param5="None", param6="None", param7="None"):
    global conn
    global cursor
    if (arguments.debug): print("Starting db_manager() function."+"\n\r"+"Current db_function is: "+db_function+".")


### CONNECT
    if (db_function == 'connect'):
        try:
            conn =  mysql.connector.connect(buffered=True, user=config['sql_user'], password=config['sql_pass'], host=config['db_server'], database=config['db_name'])
            cursor = conn.cursor()
            if(conn):
                status = "Success: Connection to SQL-server succeed."
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                status = "Error: Could not connect to SQL-server! Something is wrong with your user name or password."
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                status = "Error: Could not connect to SQL-server! Database does not exist."
            else:
                status = "Error: Could not connect to SQL-server! Error message: "+err

        return status

### haka_user_management
    if (db_function == 'haka_user_management'):
        uid=param1
        username=param2
        firstname=param3
        lastname=param4
        hireDate=param5
        mail=param6
        phone=param7

        try:
            cursor.execute(('SELECT * FROM users WHERE haka_uid=%s'), (uid,))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error in fetching users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
        row=cursor.fetchone()

        if (row is not None):
            if arguments.debug: print("\n\r"+"User "+firstname+" "+lastname+" ("+uid+") exists in the database.")
            cursor.execute(('UPDATE users SET exists_haka_flag=%s WHERE haka_uid=%s'), ('1', uid))
            conn.commit()
            if (row[3] == lastname):
                if arguments.debug: print("Lastname "+row[3]+" has not changed")
            else:
                try:
                    cursor.execute(('UPDATE users SET username=%s, lastname=%s, updated_flag=%s WHERE haka_uid=%s'), (username, lastname, '1', uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Lastname updated from "+row[3]+" to "+lastname+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating lastname from "+row[3]+" to "+lastname+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])
            if (row[4] == firstname):
                if(arguments.debug): print("Firstname "+row[4]+" has not changed.")
            else:
                try:
                    cursor.execute(('UPDATE users SET username=%s, firstname=%s, updated_flag=%s WHERE haka_uid=%s'), (username, firstname, '1', uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Firstname updated from "+row[4]+" to "+firstname+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating firstname from "+row[4]+" to "+firstname+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

            if (row[6] == mail):
                if arguments.debug: print("Mail "+row[6]+" has not changed.")
            else:
                try:
                    cursor.execute(('UPDATE users SET mail=%s, updated_flag=%s WHERE haka_uid=%s'), (mail, '1', uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Mail updated from "+row[6]+" to "+mail+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating mail from "+row[6]+" to "+mail+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

            if (row[7]  == phone):
                if arguments.debug: print("Phone "+row[7]+" has not changed.")
            else:
                try:
                    cursor.execute(('UPDATE users SET phone=%s, updated_flag=%s WHERE haka_uid=%s'), (phone, '1', uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Phone updated from "+row[7]+" to "+phone+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating phone from "+row[7]+" to "+phone+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

        else:
            if(arguments.debug or arguments.verbose): print("\n\r"+"User "+firstname+" "+lastname+" ("+uid+") does not exist in the database."+"\n\r"+"Creating...")
            try:
                cursor.execute(('INSERT INTO users (haka_uid, username, lastname, firstname, hireDate, mail, phone, exists_haka_flag) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'), (uid, username, lastname, firstname, hireDate, mail, phone, '1'))
                conn.commit()

            except mysql.connector.Error as err:
                    error_msg.append("Error in creating user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])


### aad_new_users
    if (db_function == 'aad_new_users'):
        try:
             cursor.execute('SELECT haka_uid,username,lastname,firstname,hireDate,phone,mail FROM users WHERE aad_uuid IS NULL')
             conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting new users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        row=cursor.fetchall()
        if (row is not None):
           return row


### aad_created_users
    if (db_function == 'aad_created_users'):
        uid=param1
        aad_uuid=param2
        if (uid is not None or aad_uuid is not None):
            try:
                if arguments.verbose: print("haka_uid: "+uid+" has been created to Azure Active Directory as: "+aad_uuid)
                cursor.execute(('UPDATE users SET aad_uuid=%s, new_user_flag=%s WHERE haka_uid=%s'), (aad_uuid, '1', uid))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error in updating new Azure Acitve Directory UUID value for user "+uid+" "+aad_uuid+". Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
            return


### aad_update_users
    if (db_function == 'aad_update_users'):
        try:
            cursor.execute(('SELECT aad_uuid,username,lastname,firstname,phone,mail FROM users WHERE updated_flag=%s'), ('1',))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting updated users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        row=cursor.fetchall()
        if (row is not None):
            return row
        return


### aad_update_groups
    if (db_function == 'aad_update_groups'):

        try:
            cursor.execute(("SELECT users.aad_uuid, users.firstname, users.lastname, groups.haka_group, groupmap.aad_gid, groupmap.mode FROM users LEFT JOIN groups ON groups.haka_uid=users.haka_uid LEFT JOIN groupmap ON groups.haka_group=groupmap.haka_group WHERE groups.updated_flag=%s AND users.aad_uuid IS NOT NULL;"), ('1',))
            conn.commit()

        except mysql.connector.Error as err:
            error_msg.append("Error selecting groups from database that have previously been updated in HAKA. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        row=cursor.fetchall()
        if (row is not None):
            return row
        return


### aad_delete_users
    if (db_function == 'aad_delete_users'):
        try:
            cursor.execute('SELECT aad_uuid,firstname,lastname FROM users WHERE exists_haka_flag IS NULL')
            conn.commit()

        except mysql.connector.Error as err:
            error_msg.append("Error selecting deleted users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        row=cursor.fetchall()
        if (row is not None):
            return row
        return



### aad_remove_groups
    if (db_function == 'aad_remove_groups'):
        try:
            cursor.execute('SELECT users.aad_uuid, users.firstname, users.lastname, groups.haka_group, groupmap.aad_gid FROM users LEFT JOIN groups ON groups.haka_uid=users.haka_uid LEFT JOIN groupmap ON groups.haka_group=groupmap.haka_group WHERE groups.exists_haka_flag IS NULL AND users.aad_uuid IS NOT NULL')
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting groups from database to be removed from Azure Active Directory. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        row=cursor.fetchall()
        if (row is not None):
            return row
        return

#### aad_post_users
    if (db_function == 'aad_post_users'):
        try:
            cursor.execute('SELECT aad_uuid, username, firstname, lastname, mail FROM users WHERE new_user_flag IS NOT NULL')
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting new users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        row=cursor.fetchall()
        if (row is not None):
            return row
        return


### haka_groups
    if (db_function == 'haka_groups'):
        uid=param1
        group=param2

        try:
            cursor.execute(('SELECT * FROM groups WHERE haka_uid=%s AND haka_group=%s'), (uid, group))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting groups from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])


        row=cursor.fetchone()
        if (row is not None):
            if arguments.debug: print("\n\r"+"Group "+group+" exists in the database for user "+uid+"."+"\n\r")
            try:
                cursor.execute(('UPDATE groups SET exists_haka_flag=%s WHERE haka_uid=%s AND haka_group=%s'), ('1', uid, group))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error updating flags for groups. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
        else:
            if(arguments.debug or arguments.verbose): print("Group "+group+" does not exist in the database for user "+uid+".")
            try:
                cursor.execute(('INSERT INTO groups (haka_uid, haka_group, exists_haka_flag, updated_flag) VALUES (%s, %s, %s, %s)'), (uid, group, '1', '1'))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error inserting group "+group+" for user "+uid+". Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
        return

### onedrive_add_new_drive
    if (db_function == 'onedrive_new_drive'):
        onedrive_directory_id=param1
        aad_uuid=param2

        try:
            cursor.execute(('UPDATE users SET onedrive_id=%s WHERE aad_uuid=%s'), (onedrive_directory_id, aad_uuid))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error updating newly created OneDrive ID. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

### onedrive_query_drive
    if (db_function == 'onedrive_query_drive'):

        try:
            cursor.execute(('SELECT username,onedrive_id FROM users WHERE onedrive_shared_flag IS NULL AND onedrive_id IS NOT NULL'))
            conn.commit()

            row=cursor.fetchall()
            if (row is not None):
                return row
            return

        except mysql.connector.Error as err:
            error_msg.append("Error querying OneDrive ID. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])


### onedrive_updated
    if (db_function == 'onedrive_updated'):

        try:
            cursor.execute(('SELECT firstname,lastname,onedrive_id FROM users WHERE updated_flag IS NOT NULL AND onedrive_id IS NOT NULL'))
            conn.commit()

            row=cursor.fetchall()
            if (row is not None):
                return row
            return

        except mysql.connector.Error as err:
            error_msg.append("Error updating onedrive directory name. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

### onedrive_deleted
    if (db_function == 'onedrive_deleted'):

        try:
            cursor.execute(('SELECT firstname,lastname,onedrive_id FROM users WHERE exists_haka_flag IS NULL AND onedrive_id IS NOT NULL'))
            conn.commit()

            row=cursor.fetchall()
            if (row is not None):
                return row
            return

        except mysql.connector.Error as err:
            error_msg.append("Error fetching Onedrive directories to be deleted. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])


### onedrive_update_flags
    if (db_function == 'onedrive_update_flags'):
        onedrive_id=param1

        try:
            cursor.execute(('UPDATE users SET onedrive_shared_flag=%s WHERE onedrive_id=%s'), ('1', onedrive_id))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error updating flags after successfully sharing directory. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

### cleanup
    if (db_function == 'cleanup'):
        try:
            cursor.execute("DELETE FROM users WHERE exists_haka_flag IS NULL")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error deleting non-existent users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        try:
            cursor.execute("UPDATE users SET exists_haka_flag=NULL, updated_flag=NULL, new_user_flag=NULL")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error setting user flags to NULL in database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        try:
            cursor.execute("DELETE FROM groups WHERE exists_haka_flag IS NULL")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error deleting non-existent groups from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        try:
            cursor.execute("UPDATE groups SET exists_haka_flag=NULL, updated_flag=NULL")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error setting group flags to NULL in database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        conn.close()
        return
    return


def aad_user_management(config):
    if (arguments.debug): print("\n\r"+"Starting aad_user_management() function.")

    aad_function = "aad_create_users"
    aad_connector(config, aad_function)

    aad_function = "aad_update_users"
    aad_connector(config, aad_function)


def aad_update_groups(config):
    if (arguments.debug): print("\n\r"+"Starting aad_update_groups() function.")
    aad_function = "aad_update_groups"
    aad_connector(config, aad_function)

def aad_onedrive_management(config):
    if (arguments.debug): print("\n\r"+"Starting aad_onedrive_management() function.")

    aad_function = "aad_onedrive_management"
    aad_connector(config, aad_function)

def aad_exchange_management(config):
    if (arguments.debug): print("\n\r"+"Starting aad_exchange__management() function.")

    aad_function = "aad_exchange_management"
    aad_connector(config, aad_function)


def message_handler():
    if (arguments.debug): print("Starting message_handler() function.")


def haka_connector(config, haka_function):
    global soup
    if (arguments.debug): print("Starting haka_connector() function."+"\n\r"+"Haka-function is: "+haka_function)


### haka_login
    if (haka_function == 'login'):
        params = {
            "__EVENTTARGET": "Login$btnLogin",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": soup.find('input', {'name':'__VIEWSTATE'})['value'],
            "__VIEWSTATEGENERATOR": soup.find('input', {'name':'__VIEWSTATEGENERATOR'})['value'],
            "__EVENTVALIDATION": soup.find('input', {'name':'__EVENTVALIDATION'})['value'],
            "Login$txtUsername": config["haka_user"],
            "Login$txtPassword": config["haka_pass"]
        }

        haka_login = s.post(config["haka_endpoint"]+'/kirjaudu.aspx', params)

        if(haka_login.status_code == 200):
            status = "Logging in to HAKA succeed."
            soup = BeautifulSoup(s.get(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenluettelo.ascx').text, features="lxml")
            return status
        else:
            status = "Logging in to HAKA failed."
            return status


### haka_get_users
    if (haka_function == 'haka_get_users'):
        params = {
            "__EVENTTARGET": "ctl00$cphContent$btnHae",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": soup.find('input', {'name':'__VIEWSTATE'})['value'],
            "__VIEWSTATEGENERATOR": soup.find('input', {'name':'__VIEWSTATEGENERATOR'})['value'],
            "__EVENTVALIDATION": soup.find('input', {'name':'__EVENTVALIDATION'})['value'],
            "ctl00$Pikahaku$txtHaku":"",
            "ctl00$cphContent$PalokuntaId$hdnValinta": config["haka_palokunta_id"],
            "ctl00$cphContent$HaeOsastotButton": "Hae osastot",
        }
        users = BeautifulSoup(s.post(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenluettelo.ascx', params).text, features="lxml")

# Get osastot

        params = {
            "__EVENTTARGET": "ctl00$cphContent$btnHae",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": users.find('input', {'name':'__VIEWSTATE'})['value'],
            "__VIEWSTATEGENERATOR": users.find('input', {'name':'__VIEWSTATEGENERATOR'})['value'],
            "__EVENTVALIDATION": users.find('input', {'name':'__EVENTVALIDATION'})['value'],
            "ctl00$Pikahaku$txtHaku":"",
            "ctl00$cphContent$lbJasenlajit$lbListBox":"10",
            "ctl00$cphContent$PalokuntaId$hdnValinta": "80377"
        }
        users = BeautifulSoup(s.post(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenluettelo.ascx', params).text, features="lxml")
        table = users.find('table')
        rows = table.findChildren('tr')
        data = list()
        uid = []
        name = []
        hireDate = []
        phone = []
        mail = []

        for row in rows[1:]:
            uid.append(row.findAll('td')[1])
            name.append(row.findAll('td')[2])
            hireDate.append(row.findAll('td')[6])
            phone.append(row.findAll('td')[7])
            mail.append(row.findAll('td')[8])

        for uid, name, hireDate, phone, mail in zip(uid, name, hireDate, phone, mail):
            # Parse HAKA uid
            uid = (str(uid.text)).strip()
            # Parse name
            name = (str(name.text)).strip()
            data = name.split(" ")
            # Create displayname out of name
            firstname = str(data[1])
            lastname = str(data[0])
            # Replace scandic letters with regular, for username purposes
            username = str(data[1].casefold().replace("ö","o").replace("ä","a").replace("å","a"))+"."+str(data[0].casefold().replace("ö","o").replace("ä","a").replace("å","a"))
            hireDate = (str(hireDate.text)).strip().split(".")
            if hireDate:
                hireDate = hireDate[2]+"-"+hireDate[1].zfill(2)+"-"+hireDate[0].zfill(2)

            # Choose the first telephone number from HAKA, if multiple given.
            phone = re.split(r', |,|;', str(phone.text).strip())
            phone = phone[0]
            # Remove special characters from telephone number.
            phone = ''.join(i for i in phone if i.isdigit())
            # If phone number even exists, replace leading 0 with 358 and insert leading + for numbers
            if phone != "":
                phone = "+"+(('358'+phone.lstrip('0')) if phone.startswith('0') else phone)

            # Validate email addess
            mail = str(mail.text).strip()
            mail = "" if not re.search('^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$', mail) else mail

            db_function = "haka_user_management"
            db_manager(db_function,config,uid,username,firstname,lastname,hireDate,mail,phone)



### haka_groups

    if (haka_function == 'haka_groups'):
        accepted_groups = {'1. varapäällikkö', '2. varapäällikkö', 'Ajoneuvokalustomestari/-vastaava', 'Hallituksen jäsen', 'Kalustomestari/-vastaava', 'Koulutuspäällikkö', 'Nuoriso-osaston johtaja', 'Nuoriso-osaston kouluttaja', 'Nuoriso-osaston varajohtaja', 'Palokunnan päällikkö', 'Puheenjohtaja', 'Rahastonhoitaja', 'Ryhmänjohtaja', 'Savusukellusvastaava', 'Savusukeltaja', 'Sihteeri', 'Talonmies', 'Tiedotusmestari/-vastaava', 'Varapuheenjohtaja', 'Varustemestari/-vastaava', 'Veteraaniosaston johtaja'}
        osastot = [config["haka_halytysosasto_id"],config["haka_jarjestoosasto_id"]]
        for osasto in osastot:

            soup = BeautifulSoup(s.post(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenet.ascx').text, features="lxml")

            params = {
                "__EVENTTARGET": "ctl00$cphContent$btnHae",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": soup.find('input', {'name':'__VIEWSTATE'})['value'],
                "__VIEWSTATEGENERATOR": soup.find('input', {'name':'__VIEWSTATEGENERATOR'})['value'],
                "__EVENTVALIDATION": soup.find('input', {'name':'__EVENTVALIDATION'})['value'],
                "ctl00$Pikahaku$txtHaku":"",
                "ctl00$cphContent$PalokuntaId$hdnValinta": config["haka_palokunta_id"],
                "ctl00$cphContent$HaeOsastotButton": "Hae osastot",
            }

            roles = BeautifulSoup(s.post(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenet.ascx', params).text, features="lxml")

            params = {
                "__EVENTTARGET": "ctl00$cphContent$btnHae",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": roles.find('input', {'name':'__VIEWSTATE'})['value'],
                "__VIEWSTATEGENERATOR": roles.find('input', {'name':'__VIEWSTATEGENERATOR'})['value'],
                "__EVENTVALIDATION": roles.find('input', {'name':'__EVENTVALIDATION'})['value'],
                "ctl00$Pikahaku$txtHaku":"",
                "ctl00$cphContent$PalokuntaId$hdnValinta": config["haka_palokunta_id"],
                "ctl00$cphContent$OsastotListBox$lbListBox": osasto
            }

            roles = BeautifulSoup(s.post(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenet.ascx', params).text, features="lxml")

            table = roles.find('table')
            rows = roles.findChildren('tr')
            data = list()
            roles = []
            uid = []



            for row in rows[1:]:
                roles.append(row.findAll('td')[3])
                uid.append(row.findAll('td')[15])

            for uid, roles in zip(uid, roles):
                # Parse HAKA uid
                uid = (str(uid.text)).strip()
                if(osasto == config["haka_halytysosasto_id"]):
                    db_function = "haka_groups"
                    group = "Hälytysosasto"
                    db_manager(db_function,config,uid,group)

                if(osasto == config["haka_jarjestoosasto_id"]):
                    db_function = "haka_groups"
                    group = "Järjestöosasto"
                    db_manager(db_function,config,uid,group)

                roles = (str(roles.text)).strip().split(",")
                for role in roles:
                    role=role.strip()
                    if role in accepted_groups:
                        db_function = "haka_groups"
                        group = role
                        db_manager(db_function,config,uid,group)


def aad_connector(config, aad_function):
    global aad_access_token
    global app
    if (arguments.debug):  print("Starting aad_connector() function."+"\r\n"+"Current aad_function: "+aad_function)

# LOGIN FUNCTIONALITY
    if (aad_function == 'login'):

# Create a preferably long-lived app instance which maintains a token cache.
        app = msal.ConfidentialClientApplication(
            config["client_id"], authority=config["authority"],
            client_credential=config["secret"],
        )

# The pattern to acquire a token looks like this.
        result = None
        result = app.acquire_token_silent(config["scope"], account=None)

        if not result:
            logging.info("No suitable token exists in cache. Let's get a new one from AAD.")
            result = app.acquire_token_for_client(scopes=config["scope"])

        if "access_token" in result:
            aad_access_token=result["access_token"]
            status = "Logging in to Azure Active Directory succeed."
            return status

        else:
            status = "Logging in to Azure Active Directory failed!"
            return status

### aad_create_users

    if (aad_function == 'aad_create_users'):
        db_function = "aad_new_users"
        aad_new_users=db_manager(db_function,config)
        if aad_new_users is not None:

            for row in aad_new_users:
                mail = []
                haka_uid=str(row[0])
                username=row[1]
                firstname=row[3]
                lastname=row[2]
                phone=row[5] if row[5] else " "
                mail.append(row[6]) if (row[6]) else " "
                hireDate=row[4].isoformat()+"Z"
 # Create random passowrd for user.
                password = passwordGen(14)
                data = {
                     "accountEnabled": "true",
                     "givenName": firstname,
                     "surname": lastname,
                     "displayName": firstname+" "+lastname,
                     "userPrincipalName": username+"@"+config["domain"],
                     "mailNickname": username,
                     "otherMails": mail,
                     "mobilePhone": phone,
                     "passwordProfile" : {
                         "forceChangePasswordNextSignIn": "true",
                         "password": password+"Ab1!"
                     }
                }

# Create user
                if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+haka_uid+") does not exist in Azure Active Directory."+"\n\r"+"Creating...")
                try:
                    aad_create_user=(s.post(config["aad_endpoint"]+'/users', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                    if (aad_create_user.status_code == 201):
                        if (arguments.verbose or arguments.debug): print("Success."+"\n\r")
                    else:
                        if (arguments.verbose or arguments.debug):
                            print("Creating user "+firstname+" "+lastname+" ("+haka_uid+") failed."+"\n\r"+"Continuing..."+"\n\r")
                            print("HTTP Status code: "+str(aad_create_user.status_code))
                            print(json.loads((aad_create_user.content).decode("utf8")))
                    new_users = json.loads((aad_create_user.content).decode("utf-8"))
                    aad_uuid=new_users['id']
                    aad_update_user=(s.patch(config["aad_endpoint"]+'/users/'+aad_uuid, json={"hireDate": hireDate}, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))

# Add user to global groups
                    if (arguments.verbose or arguments.debug): print("Adding user "+firstname+" "+lastname+" ("+aad_uuid+") to global groups."+"\n\r"+"Updating...")
                    aad_update_group=(s.post(config["aad_endpoint"]+'/groups/'+config["aad_palokunta_id"]+"/members/$ref", json={"@odata.id": "https://graph.microsoft.com/v1.0/users/"+aad_uuid}, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                    if(aad_update_group.status_code == 204 or aad_update_group.status_code == 201):
                        if (arguments.verbose or arguments.debug): print("Addition of "+firstname+" "+lastname+" ("+aad_uuid+") to Palokunta succeed.")
                    else:
                        if (arguments.verbose or arguments.debug): print("Addition of "+firstname+" "+lastname+" ("+aad_uuid+") to Palokunta failed.")
                        if (arguments.verbose or arguments.debug): print(json.loads(aad_update_group.content).decode("utf8"))

# Allocate basic Office 365 E1 license
                    aad_update_group=(s.post(config["aad_endpoint"]+'/groups/'+config["aad_app_Office-365-E1_id"]+"/members/$ref", json={"@odata.id": "https://graph.microsoft.com/v1.0/users/"+aad_uuid}, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                    if(aad_update_group.status_code == 204 or aad_update_group.status_code == 201):
                        if (arguments.verbose or arguments.debug): print("Allocating Office 365 E1 license to "+firstname+" "+lastname+" ("+aad_uuid+") succeed.")
                    else:
                        if (arguments.verbose or arguments.debug): print("Allocation of Office 365 E1 license to "+firstname+" "+lastname+" ("+aad_uuid+") failed.")
                        if (arguments.verbose or arguments.debug): print(aad_update_group.content)


                    db_function = "aad_created_users"
                    db_manager(db_function,config,haka_uid,aad_uuid)


                except:
                    pass

### aad_update_users
    if (aad_function == 'aad_update_users'):

        db_function = "aad_update_users"
        aad_updated_users=db_manager(db_function,config)

        for row in aad_updated_users:
            mail = []
            aad_uuid=str(row[0])
            username=row[1]
            firstname=row[3]
            lastname=row[2]
            phone=row[4] if row[4] else " "
            mail.append(row[5]) if row[5] else " "

            data = {
                 "givenName": firstname,
                 "surname": lastname,
                 "displayName": firstname+" "+lastname,
                 "userPrincipalName": username+"@"+config["domain"],
                 "mailNickname": username,
                 "otherMails": mail,
                 "mobilePhone": phone,
            }

            if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") has been updated in database.."+"\n\r"+"Updating...")
            aad_update_user=(s.patch(config["aad_endpoint"]+'/users/'+aad_uuid, json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
            if(aad_update_user.status_code == 204):
                if (arguments.verbose or arguments.debug): print("Update of "+firstname+" "+lastname+" ("+aad_uuid+") successful!")

            else:
                if (arguments.verbose or arguments.debug): print("Error in updating "+firstname+" "+lastname+" ("+aad_uuid+").")
                if (arguments.debug): print(json.loads((aad_update_user.content).decode("utf8")))


### aad_update_groups
    if (aad_function == 'aad_update_groups'):
        db_function = "aad_update_groups"
        aad_updated_groups=db_manager(db_function,config)

        for row in aad_updated_groups:
            aad_uuid=str(row[0])
            firstname=row[1]
            lastname=row[2]
            group=row[3]
            aad_gid=row[4]
            mode=row[5]


            data = {
                 "@odata.id": "https://graph.microsoft.com/v1.0/users/"+aad_uuid
            }

            if(mode == "member"):
                if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") is member of "+group+"..."+"\n\r"+"Updating membership...")
                aad_update_group=(s.post(config["aad_endpoint"]+'/groups/'+aad_gid+"/members/$ref", json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if(aad_update_group.status_code == 204):
                    if (arguments.verbose or arguments.debug): print("Setting membership for "+firstname+" "+lastname+" ("+aad_uuid+") to "+group+" successful."+"\n\r")
                else:
                    if (arguments.verbose or arguments.debug): print("Error setting membership for "+firstname+" "+lastname+" ("+aad_uuid+") to group "+group+"."+"\n\r")
                    if (arguments.debug): print(json.loads((aad_update_group.content).decode("utf8")))
            if(mode == "owner"):
                if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") is owner of "+group+"..."+"\n\r"+"Updating ownership...")
                aad_update_group=(s.post(config["aad_endpoint"]+'/groups/'+aad_gid+"/owners/$ref", json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if(aad_update_group.status_code == 204):
                    if (arguments.verbose or arguments.debug): print("Setting ownership for "+firstname+" "+lastname+" ("+aad_uuid+") to "+group+" successful."+"\n\r")
                else:
                    if (arguments.verbose or arguments.debug): print("Error setting owenership for "+firstname+" "+lastname+" ("+aad_uuid+") to group "+group+"."+"\n\r")
                    if (arguments.debug): print(json.loads((aad_update_group.content).decode("utf8")))


### aad_delete_users
    if (aad_function == 'aad_delete_users'):

        db_function = "aad_delete_users"
        aad_deleted_users=db_manager(db_function,config)
        if aad_deleted_users is not None:

            for row in aad_deleted_users:
                aad_uuid=str(row[0])
                firstname=row[1]
                lastname=row[2]

                if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") has been deleted in database.."+"\n\r"+"Deleting from Azure Active Directory...")
                aad_delete_user=(s.delete(config["aad_endpoint"]+'/users/'+aad_uuid, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if(aad_delete_user.status_code == 204):
                    if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") deleted successfully!")
                else:
                    if (arguments.verbose or arguments.debug): print("Error in deleting "+firstname+" "+lastname+" ("+aad_uuid+").")
                    if (arguments.debug): print(json.loads((aad_delete_user.content).decode("utf8")))

### aad_remove_groups
    if (aad_function == 'aad_remove_groups'):
        db_function = "aad_remove_groups"
        aad_removed_groups=db_manager(db_function,config)

        if aad_removed_groups is not None:
            for row in aad_removed_groups:
                aad_uuid=str(row[0])
                firstname=row[1]
                lastname=row[2]
                group=row[3]
                aad_gid=row[4]


                if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") is not member or owner of "+group+" anymore..."+"\n\r"+"Updating membership...")
                aad_remove_group=(s.delete(config["aad_endpoint"]+'/groups/'+aad_gid+"/members/"+aad_uuid+"/$ref", headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if(aad_remove_group.status_code == 204):
                    if (arguments.verbose or arguments.debug): print("Removing membership or ownership for "+firstname+" "+lastname+" ("+aad_uuid+") to "+group+" successful."+"\n\r")
                else:
                    if (arguments.verbose or arguments.debug): print("Error removing membership or owenership for "+firstname+" "+lastname+" ("+aad_uuid+") from group "+group+"."+"\n\r")
                    if (arguments.debug): print(json.loads((aad_remove_group.content).decode("utf8")))

        else:
            return

### Onedrive create directory
    if (aad_function == 'aad_onedrive_management'):
        db_function = "aad_post_users"
        aad_post_users=db_manager(db_function,config)
        if aad_post_users is not None:
            for row in aad_post_users:
                aad_uuid=str(row[0])
                username=row[1]
                firstname=row[2]
                lastname=row[3]
                mail=row[4]

                data = {
                     "name": lastname+" "+firstname,
                     "folder": { },
                     "@microsoft.graph.conflictBehavior": "fail"
                }

                if (arguments.verbose or arguments.debug): print("Creating a OneDrive directory and sharing it to "+firstname+" "+lastname+" ("+aad_uuid+").")

                onedrive_create_directory=(s.post(config["aad_endpoint"]+'users/'+config["aad_onedrive-user"]+'/drives/'+config["aad_onedrive-drive_id"]+'/root:/Documents/J%C3%A4senet:/children', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                onedrive_directory = json.loads((onedrive_create_directory.content).decode("utf-8"))
#                try:
                if (onedrive_create_directory.status_code == 201 or onedrive_create_directory.status_code == 200):
                    if (arguments.verbose or arguments.debug): print("Directory created successfully."+"\n\r")
                    db_function = "onedrive_new_drive"
                    db_manager(db_function,config,onedrive_directory['id'],aad_uuid)
                else:
                    if (arguments.verbose or arguments.debug): print("Directory creation failed!"+"\n\r")
                    if (arguments.verbose or arguments.debug): print(onedrive_create_directory.status_code)
                    if (arguments.verbose or arguments.debug): print(json.loads((onedrive_create_directory.content).decode("utf8")))

#Share the drive if it has not yet been shared.
        db_function = "onedrive_query_drive"
        shareable_directories=db_manager(db_function,config)
        if shareable_directories is not None:
            for row in shareable_directories:
                username=row[0]
                onedrive_id=row[1]
                data = {
                         "recipients": [
                           {
                              "email": username+"@"+config["domain"]
                           }
                        ],
                        "message": "Paloaseman tietokoneilla olevat tiedostosi.",
                        "requireSignIn": "true",
                        "sendInvitation": "true",
                        "roles": [ "write" ]
                    }

                onedrive_share_drive=(s.post(config["aad_endpoint"]+'drives/'+config["aad_onedrive-drive_id"]+'/items/'+onedrive_id+'/invite', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if (onedrive_share_drive.status_code == 200 or onedrive_share_drive.status_code == 201):
                    if (arguments.verbose or arguments.debug): print("Directory shared successfully to "+username+"."+"\n\r")
                    db_function = "onedrive_update_flags"
                    db_manager(db_function,config,onedrive_id)

                else:
                    if (arguments.debug): print("Directory sharing failed!"+"\n\r")
                    if (arguments.debug): print(onedrive_share_drive.status_code)
                    if (arguments.debug): print(json.loads((onedrive_share_drive.content).decode("utf8")))

#Update directory if name has been changed in HAKA
        db_function = "onedrive_updated"
        update_directories=db_manager(db_function,config)
        if update_directories is not None:
            for row in update_directories:
                firstname=row[0]
                lastname=row[1]
                onedrive_id=row[2]
                data = {
                          "name": lastname+" "+firstname
                    }

                onedrive_update_directory=(s.patch(config["aad_endpoint"]+'drives/'+config["aad_onedrive-drive_id"]+'/items/'+onedrive_id, json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if (onedrive_update_directory.status_code == 200 or onedrive_share_drive.status_code == 201):
                    if (arguments.verbose or arguments.debug): print("Directory name successfully chanded to "+lastname+" "+firstname+"."+"\n\r")

                else:
                    if (arguments.verbose or arguments.debug): print("Updating directory name failed!"+"\n\r")
                    if (arguments.debug): print(onedrive_share_drive.status_code)
                    if (arguments.debug): print(json.loads((onedrive_share_drive.content).decode("utf8")))

#Delete directory if user does not exist in HAKA
        db_function = "onedrive_deleted"
        delete_directories=db_manager(db_function,config)
        if delete_directories is not None:
            for row in delete_directories:
                firstname=row[0]
                firstname=row[1]
                onedrive_id=row[2]

                onedrive_delete_directory=(s.delete(config["aad_endpoint"]+'drives/'+config["aad_onedrive-drive_id"]+'/items/'+onedrive_id, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if (onedrive_delete_directory.status_code == 204):
                    if (arguments.verbose or arguments.debug): print("Directory "+lastname+" "+firstname+" successfully deleted."+"\n\r")

                else:
                    if (arguments.verbose or arguments.debug): print("Deleting directory "+lastname+" "+firstname+" failed!"+"\n\r")
                    if (arguments.debug): print(onedrive_share_drive.status_code)
                    if (arguments.debug): print(json.loads((onedrive_share_drive.content).decode("utf8")))

        else:
            return

    if (aad_function == 'aad_exchange_management'):
        db_function = "aad_post_users"
        aad_post_users=db_manager(db_function,config)
        forward_succeed=0

        if aad_post_users != []:
            countdown(600)
            while (forward_succeed != 1):
                if (arguments.debug): print("Going to wait for a while to ensure that Exchange Online"+"\n\r"+"has been able to provision the new mailboxes."+"\n\r")

                for row in aad_post_users:
                    aad_uuid=str(row[0])
                    username=row[1]
                    firstname=row[2]
                    lastname=row[3]
                    mail=row[4]

                    data = {
                         "displayName": "Oletusvälitys",
                         "sequence": "2",
                         "isEnabled": "true",
                         "actions": {
                             "forwardTo": [
                                 {
                                 "emailAddress": {
                                     "name": firstname+" "+lastname,
                                     "address": mail
                                     }
                                 }
                             ],
                         "stopProcessingRules": "true"
                         }
                    }

# Set automatic forwarding
                    if (arguments.verbose or arguments.debug): print("Adding automatic forwarding from "+username+"@"+config["domain"]+" to "+row[4]+".")
                    if (row[4]):
                        aad_set_auto_forward=(s.post(config["aad_endpoint"]+'/users/'+aad_uuid+'/mailFolders/inbox/messageRules', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                        if(aad_set_auto_forward.status_code == 200 or aad_set_auto_forward.status_code == 201):
                            forward_succeed = 1
                            if (arguments.verbose or arguments.debug): print("Automatic forwarding succeed."+"\n\r")
                        else:
                            directory_creation = 0
                            if (arguments.verbose or arguments.debug):
                                print("Automatic forwarding failed.")
                                print("HTTP Status code: "+str(aad_set_auto_forward.status_code))
                                print(json.loads((aad_set_auto_forward.content).decode("utf8")))
                            countdown(300)
            else:
                return



def main():
    config = json.load(open(arguments.config))

    if (arguments.debug): print("\n\r"+"Starting main() function.")

    init(config)
    if (arguments.debug): print(datetime.now() - startTime)
    haka_get_users(config)
    if (arguments.debug): print(datetime.now() - startTime)
    haka_get_groups(config)
    if (arguments.debug): print(datetime.now() - startTime)
    aad_user_management(config)
    if (arguments.debug): print(datetime.now() - startTime)
    aad_exchange_management(config)
    if (arguments.debug): print(datetime.now() - startTime)
    aad_update_groups(config)
    if (arguments.debug): print(datetime.now() - startTime)
    aad_onedrive_management(config)
    if (arguments.debug): print(datetime.now() - startTime)
    cleanup(config)
    if (arguments.debug): print(datetime.now() - startTime)



main()
