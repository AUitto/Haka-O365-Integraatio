#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# CreateUsers.py v. 2.2.1
#
# Date 17.4.2020

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

def delete_user(config, param1="None", param2="None", param3="None", param4="None", param5="None"):
    haka_uid=param1
    aad_uuid=param2
    firstname=param3
    lastname=param4
    onedrive_id=param5

### Delete from AAD
    if (arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") has been disabled for 30 days..."+"\n\r"+"Deleting from Azure Active Directory...")
    aad_delete_user=(s.delete(config["aad_endpoint"]+'/users/'+aad_uuid, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))

    if(aad_delete_user.status_code == 204):
        if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") deleted successfully!")
    else:
        if (arguments.verbose or arguments.debug): print("Error in deleting "+firstname+" "+lastname+" ("+aad_uuid+").")
        if (arguments.debug): print(json.loads((aad_delete_user.content).decode("utf8")))

    if onedrive_id:
        onedrive_delete_directory=(s.delete(config["aad_endpoint"]+'drives/'+config["aad_onedrive-drive_id"]+'/items/'+onedrive_id, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))

        if (onedrive_delete_directory.status_code == 204 or onedrive_delete_directory.status_code == 201 or onedrive_delete_directory.status_code == 200):
            if (arguments.verbose or arguments.debug): print("Directory "+lastname+" "+firstname+" successfully deleted."+"\n\r")
        else:
            if (arguments.verbose or arguments.debug): print("Deleting directory "+lastname+" "+firstname+" failed!"+"\n\r")
            if (arguments.debug): print(onedrive_delete_directory.status_code)
            if (arguments.debug): print(json.loads((onedrive_delete_directory.content).decode("utf8")))




def cleanup(config):
    if (arguments.debug): print("\n\r"+"Starting cleanup() function.")

    aad_function = "aad_remove_groups"
    aad_connector(config, aad_function)

    aad_function = "aad_disable_users"
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
                try:
                    cursor.execute(('SHOW OPEN TABLES WHERE in_use>%s'), ('0',))
                    conn.commit()

                except mysql.connector.Error as err:
                    error_msg.append("Error: Cannot fetch locked tables. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    return status

                row=cursor.fetchone()
                if (row is None):
                    try:
                        cursor.execute('LOCK TABLE users WRITE, groups WRITE, groupmap READ, status WRITE')
                        conn.commit()

                    except mysql.connector.Error as err:
                        error_msg.append("Error: Can not lock tables. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                        return status
                else:
                    error_msg.append("Error: Can not lock tables. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    return status

        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                status = "Error: Could not connect to SQL-server! Something is wrong with your user name or password."
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                status = "Error: Could not connect to SQL-server! Database does not exist."
            else:
                status = "Error: Could not connect to SQL-server! Error message: "+str(err)

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
            cursor.execute(('INSERT INTO status (haka_uid, status) VALUES(%s, %s)'), (uid, "exists"))
            conn.commit()

            if (row[3] == lastname):
                if arguments.debug: print("Lastname "+row[3]+" has not changed")
            else:
                try:
                    cursor.execute(('UPDATE users SET username=%s, lastname=%s WHERE haka_uid=%s'), (username, lastname, uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Lastname updated from "+row[3]+" to "+lastname+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating lastname from "+row[3]+" to "+lastname+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])
                try:
                    cursor.execute(('INSERT INTO status (haka_uid, modified_key, status) VALUES(%s, %s, %s)'), (uid, 'lastname', 'updated'))
                    conn.commit()
                except mysql.connector.Error as err:
                    error_msg.append("Error in status flag for "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

            if (row[4] == firstname):
                if(arguments.debug): print("Firstname "+row[4]+" has not changed.")
            else:
                try:
                    cursor.execute(('UPDATE users SET username=%s, firstname=%s WHERE haka_uid=%s'), (username, firstname, uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Firstname updated from "+row[4]+" to "+firstname+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating firstname from "+row[4]+" to "+firstname+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])
                try:
                    cursor.execute(('INSERT INTO status (haka_uid, modified_key, status) VALUES(%s, %s, %s)'), (uid, 'firstname', 'updated'))
                    conn.commit()
                except mysql.connector.Error as err:
                    error_msg.append("Error in status flag for "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

            if (row[8] == mail):
                if arguments.debug: print("Mail "+row[8]+" has not changed.")
            else:
                try:
                    cursor.execute(('UPDATE users SET mail=%s WHERE haka_uid=%s'), (mail, uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Mail updated from "+row[8]+" to "+mail+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating mail from "+row[8]+" to "+mail+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])
                try:
                    cursor.execute(('INSERT INTO status (haka_uid, modified_key, status) VALUES(%s, %s, %s)'), (uid, 'mail', 'updated'))
                    conn.commit()
                except mysql.connector.Error as err:
                    error_msg.append("Error in status flag for "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

            if (row[9]  == phone):
                if arguments.debug: print("Phone "+row[9]+" has not changed.")
            else:
                try:
                    cursor.execute(('UPDATE users SET phone=%s WHERE haka_uid=%s'), (phone, uid))
                    conn.commit()
                    if(arguments.debug or arguments.verbose): print("Phone updated from "+row[9]+" to "+phone+".")
                except mysql.connector.Error as err:
                    error_msg.append("Error in updating phone from "+row[9]+" to "+phone+" for user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])
                try:
                    cursor.execute(('INSERT INTO status (haka_uid, modified_key, status) VALUES(%s, %s, %s)'), (uid, 'phone', 'updated'))
                    conn.commit()
                except mysql.connector.Error as err:
                    error_msg.append("Error in status flag for "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])

        else:
            if (mail or phone):
                if(arguments.debug or arguments.verbose): print("\n\r"+"User "+firstname+" "+lastname+" [	"+uid+"] does not exist in the database."+"\n\r"+"Creating...")
                try:
                    cursor.execute(('INSERT INTO users (haka_uid, username, lastname, firstname, hireDate, mail, phone) VALUES (%s, %s, %s, %s, %s, %s, %s)'), (uid, username, lastname, firstname, hireDate, mail, phone))
                    conn.commit()
                except mysql.connector.Error as err:
                        error_msg.append("Error in creating user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                        if(arguments.debug or arguments.verbose): print(error_msg[-1])
                try:
                    cursor.execute(('INSERT INTO status (haka_uid, status) VALUES(%s, %s)'), (uid, 'new'))
                    conn.commit()
                except mysql.connector.Error as err:
                    error_msg.append("Error in status flag for new user "+firstname+" "+lastname+" ("+uid+"). Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                    if(arguments.debug or arguments.verbose): print(error_msg[-1])
            else:
                if(arguments.debug): print("\n\r"+"User "+firstname+" "+lastname+" ("+uid+") did not have either mail or phone set."+"\n\r")

### haka_verify_user
    if (db_function == 'haka_verify_user'):
        uid=param1
        try:
            cursor.execute(('SELECT * FROM users WHERE haka_uid=%s'), (uid,))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        row=cursor.fetchall()
        if (row is not None):
           return row


### aad_new_users
    if (db_function == 'aad_new_users'):
        try:
            cursor.execute(('SELECT users.haka_uid, users.aad_uuid, users.username, users.lastname, users.firstname, users.hireDate, users.phone, users.mail FROM users LEFT JOIN status ON users.haka_uid=status.haka_uid WHERE status=%s'), ('new',))
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
            if arguments.verbose: print("haka_uid ["+uid+"] has been created to Azure Active Directory as ("+aad_uuid+").")
            try:
                cursor.execute(('UPDATE users SET aad_uuid=%s WHERE haka_uid=%s'), (aad_uuid, uid))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error in updating new Azure Acitve Directory UUID value for user "+uid+" "+aad_uuid+". Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
            return


### aad_update_users
    if (db_function == 'aad_update_users'):
        uid = ""
        key = ""
        payload = {}
        try:
            cursor.execute(('SELECT DISTINCT haka_uid FROM status WHERE status=%s'), ('updated',))
            conn.commit()

        except mysql.connector.Error as err:
            error_msg.append("Error selecting updated users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        uids=cursor.fetchall()
        for uid in uids:
            temp={}
            temp["haka_uid"]=str(uid[0])

            try:
                uid=uid[0]
                cursor.execute(('SELECT firstname, lastname, aad_uuid FROM users WHERE haka_uid=%s'), (uid,))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error selecting modified keys from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
            row=cursor.fetchone()
            firstname=row[0]
            lastname=row[1]
            aad_uuid=row[2]
            temp["firstname"]=firstname
            temp["lastname"]=lastname
            temp["aad_uuid"]=aad_uuid

            try:
                cursor.execute(('SELECT modified_key FROM status WHERE haka_uid=%s AND modified_key IS NOT NULL'), (uid,))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error selecting modified keys from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])

            keys=cursor.fetchall()
            for key in keys:
                if (key[0] == "groups"):
                    try:
                        cursor.execute(('SELECT haka_group FROM groups WHERE haka_uid=%s AND updated_flag IS NOT NULL'), (uid,))
                    except mysql.connector.Error as err:
                        error_msg.append("Error selecting updated groups from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                        if(arguments.debug or arguments.verbose): print(error_msg[-1])
                    value=cursor.fetchall()
                    temp[key[0]]=value
                else:
                    try:
                        cursor.execute(('SELECT '+str(key[0])+' FROM users WHERE haka_uid=%s'), (uid,))
                    except mysql.connector.Error as err:
                        error_msg.append("Error selecting updated value from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                        if(arguments.debug or arguments.verbose): print(error_msg[-1])
                    value=cursor.fetchone()
                    temp[key[0]]=value[0]

            payload[uid]=temp


        if (payload != {}):
           return payload
        else:
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

### aad_disable_users
    if (db_function == 'aad_disable_users'):
        try:
            cursor.execute('SELECT users.aad_uuid, users.haka_uid, users.username, users.firstname, users.lastname FROM users NATURAL LEFT JOIN status WHERE status.status IS NULL AND users.disabled_date IS NULL')
            conn.commit()

        except mysql.connector.Error as err:
            error_msg.append("Error selecting users to be disabled from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        row=cursor.fetchall()
        if (row is not None):
            return row
        return

### aad_user_disabled
    if (db_function == 'aad_user_disabled'):
        aad_uuid=param1
        try:
            cursor.execute(('UPDATE users SET disabled_date=%s WHERE aad_uuid=%s'), (datetime.now(), aad_uuid))
            conn.commit()

        except mysql.connector.Error as err:
            error_msg.append("Error selecting deleted users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        return


### aad_remove_groups
    if (db_function == 'aad_remove_groups'):
        try:
            cursor.execute('SELECT users.aad_uuid, users.haka_uid, users.firstname, users.lastname, groups.haka_group, groupmap.aad_gid FROM users LEFT JOIN groups ON groups.haka_uid=users.haka_uid LEFT JOIN groupmap ON groups.haka_group=groupmap.haka_group WHERE groups.exists_haka_flag IS NULL AND users.aad_uuid IS NOT NULL')
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error selecting groups from database to be removed from Azure Active Directory. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
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
            try:
                cursor.execute(('INSERT INTO status (haka_uid, modified_key,status) VALUES (%s, %s, %s)'), (uid, 'groups', 'updated'))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error setting updated group flag for user "+uid+". Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
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
            if (row is not None or row != []):
                return row
            return

        except mysql.connector.Error as err:
            error_msg.append("Error querying OneDrive ID. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])


### onedrive_updated
    if (db_function == 'onedrive_updated'):

        try:
            cursor.execute(('SELECT users.firstname, users.lastname, users.onedrive_id FROM users NATURAL LEFT JOIN status WHERE modified_key=%s or modified_key=%s'), ('firstname', 'lastname'))
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

            cursor.execute(('SELECT users.aad_uuid, users.firstname, users.lastname FROM users NATURAL LEFT JOIN status WHERE status.status IS NULL AND users.disabled_date IS NULL AND onedrive_id IS NOT NULL;'))
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

### db_remove_group
    if (db_function == 'db_remove_group'):
        haka_uid=param1
        group=param2

        try:
            cursor.execute(("DELETE FROM groups WHERE haka_uid=%s AND haka_group=%s"), (haka_uid, group))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error removing group. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])


### haka_roles
    if (db_function == 'haka_roles'):
        haka_uid=param1
        roles=param2
        title = " "
        education = " "
        title_list= {'1. varapäällikkö', '2. varapäällikkö', 'Koulutuspäällikkö', 'Nuoriso-osaston johtaja', 'Nuoriso-osaston varajohtaja', 'Palokunnan päällikkö', 'Puheenjohtaja', 'Ryhmänjohtaja', 'Veteraaniosaston johtaja'}
        education_list = {'Nuorempi sammutusmies', 'Sammutusmies', 'Vanhempi sammutusmies', 'Sammutusmiesharjoittelija'}

        roles = (str(roles.text)).strip().split(", ")
        for role in roles:

            if role in education_list:
                education = role
                if (title == " "): title = role

            if role in title_list:
                title = role
                if (role == "Veteraaniosaston johtaja"):
                    title = "Järjestöosaston johtaja"
                elif (role == "Ryhmänjohtaja"):
                    title = "Nimetty yksikönjohtaja"
                elif (role == "2. varapäällikkö"):
                    title = "Hälytysosaston varapäällikkö"
                elif (role == "1. varapäällikkö"):
                    title = "Hälytysosaston päällikkö"
                else:
                    title = role

        try:
            cursor.execute(("SELECT title FROM users WHERE haka_uid=%s"), (haka_uid,))
            rows=cursor.fetchone()
        except mysql.connector.Error as err:
            error_msg.append("Error fetching title. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        if (rows[0] != title):
            try:
                cursor.execute(("UPDATE users SET title=%s WHERE haka_uid=%s"), (title, haka_uid))
                conn.commit()
                if(arguments.debug): print("Title updated to: "+title+" from "+str(rows[0]))
            except mysql.connector.Error as err:
                error_msg.append("Error setting title. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
            try:
                cursor.execute(("INSERT INTO status(haka_uid, modified_key, status) VALUES(%s, %s, %s)"), (haka_uid, 'title', 'updated'))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error setting title flag on status table. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])

        try:
            cursor.execute(("SELECT education FROM users WHERE haka_uid=%s"), (haka_uid,))
            rows=cursor.fetchone()
        except mysql.connector.Error as err:
            error_msg.append("Error fetching education. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        if (rows[0] != education):
            try:
                cursor.execute(("UPDATE users SET education=%s WHERE haka_uid=%s"), (education, haka_uid))
                conn.commit()
                if(arguments.debug): print("Education updated to: "+education+" from "+str(rows[0]))
            except mysql.connector.Error as err:
                error_msg.append("Error setting education. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])
            try:
                cursor.execute(("INSERT INTO status(haka_uid, modified_key, status) VALUES(%s, %s, %s)"), (haka_uid, 'education', 'updated'))
                conn.commit()
            except mysql.connector.Error as err:
                error_msg.append("Error setting education flag on status table. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                if(arguments.debug or arguments.verbose): print(error_msg[-1])

### db_delete_user
    if (db_function == 'db_delete_user'):
        try:
            cursor.execute("SELECT haka_uid,aad_uuid,firstname,lastname,onedrive_id,disabled_date from users WHERE disabled_date IS NOT NULL")
            rows=cursor.fetchall()

            for row in rows:
                haka_uid=row[0]
                aad_uuid=str(row[1])
                firstname=row[2]
                lastname=row[3]
                onedrive_id=row[4]
                disabled_date=row[5]
                difference = datetime.now() - disabled_date
                if (difference.days > 30):
                    if(arguments.debug or arguments.verbose): print("User "+firstname+" "+lastname+" ["+str(haka_uid)+"] ("+aad_uuid+") has been disabled for 30 days. It will be deleted now.")
                    delete_user(config,haka_uid,aad_uuid,firstname,lastname,onedrive_id)
                    try:
                        cursor.execute(('INSERT INTO status (haka_uid, status) VALUES (%s, %s)'), (haka_uid, 'deleted'))
                        conn.commit()
                    except mysql.connector.Error as err:
                        error_msg.append("Error setting education flag on status table. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
                        if(arguments.debug or arguments.verbose): print(error_msg[-1])
        except mysql.connector.Error as err:
            error_msg.append("Error deleting non-existent users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])


### db_deleted_users
    if (db_function == 'db_deleted_users'):

        try:
            cursor.execute(('SELECT users.aad_uuid, users.username, users.lastname, users.firstname, users.haka_uid FROM users LEFT JOIN status ON users.haka_uid=status.haka_uid WHERE status=%s'), ('deleted',))
            conn.commit()

        except mysql.connector.Error as err:
            error_msg.append("Error selecting deleted users from database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        row=cursor.fetchall()
        if (row is not None):
           return row


### cleanup
    if (db_function == 'cleanup'):
        try:
            cursor.execute(("DELETE users FROM users LEFT JOIN status ON users.haka_uid=status.haka_uid WHERE status=%s"), ('deleted',))
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error removing deleted user from users table. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        try:
            cursor.execute("DELETE FROM status WHERE haka_uid IS NOT NULL")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error setting user flags to NULL in database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])

        try:
            cursor.execute("UPDATE groups SET exists_haka_flag=NULL, updated_flag=NULL")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error setting group flags to NULL in database. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
            if(arguments.debug or arguments.verbose): print(error_msg[-1])
        try:
            cursor.execute("UNLOCK TABLES")
            conn.commit()
        except mysql.connector.Error as err:
            error_msg.append("Error unlocking tables. Current db_function is: "+db_function+". SQL-error: "+str(err)+".")
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

    db_function = "db_delete_user"
    db_manager(db_function,config)


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
            "ctl00$cphContent$PalokuntaId$hdnValinta": config["haka_palokunta_id"]
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
        title = ""
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
                "ctl00$cphContent$OsastotListBox$lbListBox": osasto,
                "ctl00$cphContent$lstSarakkeet$1": "Rooli",
                "ctl00$cphContent$lstSarakkeet$13": "Jäsennumero"
            }

            roles = BeautifulSoup(s.post(config["haka_endpoint"]+'/Raportit/Raportti.aspx?raportti=jasenet.ascx', params).text, features="lxml")

            table = roles.find('table')
            rows = roles.findChildren('tr')
            data = list()
            name = []
            roles = []
            uid = []


            for row in rows[1:]:
                name.append(row.findAll('td')[1])
                roles.append(row.findAll('td')[2])
                uid.append(row.findAll('td')[3])

            for uid, roles in zip(uid, roles):
                db_function = "haka_verify_user"
                # Parse HAKA uid
                uid = (str(uid.text)).strip()
                user_exists=db_manager(db_function,config,uid)
                if user_exists != []:
                    if(osasto == config["haka_halytysosasto_id"]):
                        db_function = "haka_groups"
                        group = "Hälytysosasto"
                        db_manager(db_function,config,uid,group)

                    if(osasto == config["haka_jarjestoosasto_id"]):
                        db_function = "haka_groups"
                        group = "Järjestöosasto"
                        db_manager(db_function,config,uid,group)

                    db_function = "haka_roles"
                    db_manager(db_function,config,uid,roles)

                    roles = (str(roles.text)).strip().split(",")
                    for role in roles:
                        role=role.strip()
                        if role in accepted_groups:

                            db_function = "haka_groups"
                            group = role
                            db_manager(db_function,config,uid,group)




def aad_connector(config, aad_function, param1="None"):
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
                username=row[2]
                firstname=row[4]
                lastname=row[3]
                phone=row[6] if row[6] else " "
                mail.append(row[7]) if (row[7]) else " "
                hireDate=row[5].isoformat()+"Z"
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
                     "country": "fi",
                     "preferredLanguage": "fi",
                     "passwordProfile" : {
                         "forceChangePasswordNextSignIn": "true",
                         "password": password+"Ab1!"
                     }
                }

# Create user
                if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ["+haka_uid+"] does not exist in Azure Active Directory."+"\n\r"+"Creating...")
                try:
                    aad_create_user=(s.post(config["aad_endpoint"]+'/users', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                    if (aad_create_user.status_code == 201):
                        if (arguments.verbose or arguments.debug): print("Success."+"\n\r")
                    else:
                        if (arguments.verbose or arguments.debug):
                            print("Creating user "+firstname+" "+lastname+" ["+haka_uid+"] failed."+"\n\r"+"Continuing..."+"\n\r")
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

        if aad_updated_users is not None:
            firstname = ""
            lastname = ""
            username = ""
            title = ""
            aad_uuid = ""
            haka_uid = ""
            phone = ""
            mail = []
            for key,value in aad_updated_users.items():
                for k2,v2 in value.items():
                    if "aad_uuid" in k2: aad_uuid = v2
                    if "haka_uid" in k2: haka_uid = v2
                    if "username" in k2: username = v2
                    if "firstname" in k2: firstname = v2
                    if "lastname" in k2: lastname = v2
                    if "phone" in k2: phone = v2
                    if "mail" in k2: mail.append(v2)
                    if "title" in k2: title = v2

                data = {}
                if firstname: data["givenName"]=firstname
                if lastname: data["surname"]=lastname
                if firstname or lastname: data["displayName"]=firstname+" "+lastname
                if username: data["userPrincipalName"]=username+"@"+config["domain"]
                if username: data["mailNickname"]=username
                if mail: data["otherMails"]=mail
                if phone: data["mobilePhone"]=phone
                if title: data["jobTitle"]=title

                print(aad_uuid)
                if (arguments.debug): print("User "+firstname+" "+lastname+" ("+str(aad_uuid)+") has been updated in database.."+"\n\r"+"Updating...")
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

        if aad_updated_groups is not None:
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
                        if (arguments.verbose or arguments.debug): print("Error setting ownership for "+firstname+" "+lastname+" ("+aad_uuid+") to group "+group+"."+"\n\r")
                        if (arguments.debug): print(json.loads((aad_update_group.content).decode("utf8")))

### aad_disable_users
    if (aad_function == 'aad_disable_users'):

        db_function = "aad_disable_users"
        aad_disabled_users=db_manager(db_function,config)

        if aad_disabled_users is not None:

            for row in aad_disabled_users:
                aad_uuid=str(row[0])
                haka_uid=str(row[1])
                firstname=row[3]
                lastname=row[4]

                if (arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") ["+haka_uid+"] has been deleted in database.."+"\n\r"+"Disabling inf Azure Active Directory...")
                aad_disable_user=(s.patch(config["aad_endpoint"]+'/users/'+aad_uuid, json={"accountEnabled": "false"}, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                if(aad_disable_user.status_code == 204):
                    if (arguments.verbose or arguments.debug): print("User "+firstname+" "+lastname+" ("+aad_uuid+") disabled successfully!")
                    db_function = "aad_user_disabled"
                    db_manager(db_function,config,aad_uuid)

                else:
                    if (arguments.verbose or arguments.debug): print("Error in disabling "+firstname+" "+lastname+" ("+aad_uuid+").")
                    if (arguments.debug): print(json.loads((aad_disable_user.content).decode("utf8")))



### aad_remove_groups
    if (aad_function == 'aad_remove_groups'):
        db_function = "aad_remove_groups"

        aad_removed_groups=db_manager(db_function,config)
        if aad_removed_groups is not None:
            for row in aad_removed_groups:
                aad_uuid=str(row[0])
                haka_uid=row[1]
                firstname=row[2]
                lastname=row[3]
                group=row[4]
                aad_gid=row[5]


                if ( group is not None or aad_gid is not None):
                    if (arguments.debug): print("User "+str(firstname)+" "+str(lastname)+" ("+str(aad_uuid)+") is not member or owner of "+str(group)+" anymore..."+"\n\r"+"Updating membership...")
                    aad_remove_group=(s.delete(config["aad_endpoint"]+'/groups/'+aad_gid+"/members/"+aad_uuid+"/$ref", headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                    if(aad_remove_group.status_code == 204):
                        if (arguments.verbose or arguments.debug): print("Removing membership or ownership for "+firstname+" "+lastname+" ("+aad_uuid+") to "+str(group)+" successful."+"\n\r")
                        db_function = 'db_remove_group'
                        db_manager(db_function,config,haka_uid,group)
                    else:
                        if (arguments.verbose or arguments.debug): print("Error removing membership or ownership for "+firstname+" "+lastname+" ("+aad_uuid+") from group "+str(group)+"."+"\n\r")
                        if (arguments.debug): print(json.loads((aad_remove_group.content).decode("utf8")))

        else:
            return

### Onedrive create directory
    if (aad_function == 'aad_onedrive_management'):
        db_function = "aad_new_users"
        aad_new_users=db_manager(db_function,config)
        if aad_new_users !=[] or aad_new_users is not None:
            for row in aad_new_users:
                aad_uuid=str(row[1])
                username=row[2]
                firstname=row[4]
                lastname=row[3]
                mail=row[7]

                data = {
                     "name": lastname+" "+firstname,
                     "folder": { },
                     "@microsoft.graph.conflictBehavior": "fail"
                }

                if (arguments.verbose or arguments.debug): print("Creating a OneDrive directory and sharing it to "+firstname+" "+lastname+" ("+aad_uuid+").")

                onedrive_create_directory=(s.post(config["aad_endpoint"]+'users/'+config["aad_onedrive-user"]+'/drives/'+config["aad_onedrive-drive_id"]+'/root:/Documents/J%C3%A4senet:/children', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                onedrive_directory = json.loads((onedrive_create_directory.content).decode("utf-8"))

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


        if shareable_directories !=[]:

            if (arguments.debug): print("Going to wait for a while to make sure OneDrive is really ready."+"\n\r")
            if (shareable_directories is not None):
                countdown(150)
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
                if (onedrive_update_directory.status_code == 200 or onedrive_update_directory.status_code == 201):
                    if (arguments.debug): print("Directory name successfully changed to "+lastname+" "+firstname+"."+"\n\r")

                else:
                    if (arguments.verbose or arguments.debug): print("Updating directory name failed!"+"\n\r")
                    if (arguments.debug): print(onedrive_share_drive.status_code)
                    if (arguments.debug): print(json.loads((onedrive_share_drive.content).decode("utf8")))
        else:
            return


### aad_exchange_management
    if (aad_function == 'aad_exchange_management'):
        db_function = "aad_new_users"
        aad_new_users=db_manager(db_function,config)
        forward_succeed=0

        if aad_new_users != []:
            if (arguments.debug): print("Going to wait for a while to ensure that Exchange Online has been able to provision the new mailboxes."+"\n\r")
            countdown(600)

            for row in aad_new_users:
                forward_succeed = 0
                while (forward_succeed != 1):
                    aad_uuid=str(row[1])
                    username=row[2]
                    firstname=row[4]
                    lastname=row[3]
                    if (row[7]):
                        mail=row[7]

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

                    else: forward_succeed=1

# Set automatic forwarding
                    if (arguments.verbose or arguments.debug): print("Adding automatic forwarding from "+username+"@"+config["domain"]+" to "+row[7]+".")
                    if (row[7]):
                        aad_set_auto_forward=(s.post(config["aad_endpoint"]+'/users/'+aad_uuid+'/mailFolders/inbox/messageRules', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
                        if(aad_set_auto_forward.status_code == 200 or aad_set_auto_forward.status_code == 201):
                            forward_succeed = 1
                            if (arguments.verbose or arguments.debug): print("Automatic forwarding succeed."+"\n\r")
                        else:
                            forward_succeed = 0
                            if (arguments.verbose or arguments.debug):
                                print("Automatic forwarding failed.")
                                print("HTTP Status code: "+str(aad_set_auto_forward.status_code))
                                print(json.loads((aad_set_auto_forward.content).decode("utf8")))
                            countdown(300)

# aad_send_mail
    if (aad_function == 'aad_send_mail'):
        html_msg = param1

        data = {
           "message": {
              "subject": "HAKA-O365 Report",
              "body": {
              "contentType": "html",
              "content": html_msg
              },
           "toRecipients": [
              {
                 "emailAddress": {
                    "address": config["admin_email_to"]
                 }
              }
           ],
           },
           "saveToSentItems": "false"
           }
        aad_send_mail=(s.post(config["aad_endpoint"]+'/users/'+config["admin_email_from"]+'/sendMail', json.dumps(data, indent=2), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aad_access_token}))
        if (aad_send_mail.status_code == 202):
            if (arguments.debug): print("Mail sent successfully."+"\n\r")
        else:
            if (arguments.verbose or arguments.debug):
                print("HTTP Status code: "+str(aad_send_mail.status_code))
                print(json.loads((aad_send_mail.content).decode("utf8")))


            else:
                return

def message_handler(config):
    html_msg = ""
    db_function = "aad_new_users"
    new_users=db_manager(db_function,config)
    if new_users != []:
        html_msg = html_msg+"<table><tdbody><tr><td style='border: solid 1 \#000000;'>"+"\n\r"+"<p align='center'>NEW USERS</p>"
        for row in new_users:
            haka_uid=row[0]
            aad_uuid=row[1]
            username=row[2]
            lastname=row[3]
            firstname=row[4]
            html_msg = html_msg+"<tr><td style='border: solid 1 \#000000;'><p align='left'>"+str(firstname)+" "+str(lastname)+" - "+str(username)+" ("+str(aad_uuid)+") ["+str(haka_uid)+"]</p></td>"+"\n\r"
        html_msg=html_msg+"</td></tr>"+"\n\r"+"</tbody></table>"


    db_function = "aad_update_users"
    updated_users=db_manager(db_function,config)
    if updated_users is not None:
        html_msg = html_msg+"<table><tdbody><tr><td style='border: solid 1 \#000000;'>"+"\n\r"+"<p align='center'>UPDATED USERS</p>"
        firstname = ""
        lastname = ""
        username = ""
        title = ""
        aad_uuid = ""
        haka_uid = ""
        phone = ""
        groups = []
        mail = []
        for key,value in updated_users.items():
            for k2,v2 in value.items():
                if "groups" in k2: groups = v2
                if "aad_uuid" in k2: aad_uuid = v2
                if "haka_uid" in k2: haka_uid = v2
                if "username" in k2: username = v2
                if "firstname" in k2: firstname = v2
                if "lastname" in k2: lastname = v2
                if "phone" in k2: phone = v2
                if "mail" in k2: mail.append(v2)
                if "title" in k2: title = v2
            if firstname or lastname: html_msg=html_msg+"<tr><td style='border: solid 1 \#000000;'><p align='left'><strong>"+firstname+" "+lastname+" ("+aad_uuid+") ["+haka_uid+"]</strong></p>"
            if username: html_msg=html_msg+"<pre align='left'>Username: "+username+"</pre>"
            if phone: html_msg=html_msg+"<pre align='left'>Phone: "+phone+"</pre>"
            if mail: html_msg=html_msg+"<pre align='left'>Email: "+mail[0]+"</pre>"
            if title: html_msg=html_msg+"<pre align='left'>Title: "+title+"</pre>"
            if groups: html_msg=html_msg+"<pre align='left'>Groups: "+str(groups)+"</pre>"
            html_msg=html_msg+"</td></tr>"+"\n\r"
        html_msg=html_msg+"</td></tr>"+"\n\r"+"</tbody></table>"


    db_function = "aad_disable_users"
    disabled_users=db_manager(db_function,config)
    if disabled_users != []:
        html_msg = html_msg+"<table><tdbody><td style='border: solid 1 \#000000;'>"+"\n\r"+"<p align='center'>DISABLED USERS</p>"
        for row in disabled_users:
            aad_uuid=str(row[0])
            haka_uid=row[1]
            firstname=row[3]
            lastname=row[4]
            username=row[2]
            html_msg = html_msg+"<tr><td style='border: solid 1 \#000000;'><p align='left'>"+str(firstname)+" "+str(lastname)+" {"+str(username)+"} ("+str(aad_uuid)+") ["+str(haka_uid)+"]</p>"
        html_msg=html_msg+"</td></tr>"+"\n\r"+"</tbody></table>"

    db_function = "db_deleted_users"
    deleted_users=db_manager(db_function,config)
    if deleted_users != []:
        html_msg = html_msg+"<table><tdbody><td style='border: solid 1 \#000000;'>"+"\n\r"+"<p align='center'>DELETED USERS</p>"
        for row in deleted_users:
            aad_uuid=row[0]
            username=row[1]
            firstname=row[3]
            lastname=row[2]
            haka_uid=row[4]
            html_msg = html_msg+"<tr><td style='border: solid 1 \#000000;'><p align='left'>"+str(firstname)+" "+str(lastname)+" {"+str(username)+"} ("+str(aad_uuid)+") ["+str(haka_uid)+"]</p></td></tr>"

        html_msg=html_msg+"</td></tr>"+"\n\r"+"</tbody></table>"


    if html_msg:
        html_msg="<table>"+"\n\r"+"<tbody>"+"\n\r"+"<tr>"+"\n\r"+"<td>""<p align='center'><strong>O365 User Report</strong></p>"+"\n\r"+"</td>"+"\n\r"+"</tr>"+"\n\r"+"<tr>"+"\n\r"+html_msg+"</tbody></table>"
        aad_function = "aad_send_mail"
        aad_connector(config, aad_function, html_msg)



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
    message_handler(config)
    if (arguments.debug): print(datetime.now() - startTime)
    cleanup(config)
    if (arguments.debug): print(datetime.now() - startTime)


main()
