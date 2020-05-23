#!/usr/bin/python3
"""
Copyright 2020 Jon Vadney

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""
import argparse
import csv
import datetime
import flight_circle
import getpass
import json
import os
import time
import sys

# ################
# Globals
# ################
days_valid = 180
today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
_180_days_ago = today - datetime.timedelta(days=days_valid)

csv_data = None
username = None
password = None
if ('FS_USER' in os.environ): 
    username = os.environ.get('FS_USER')
if ('FS_PASS' in os.environ):
    password = os.environ.get('FS_PASS')

fbo_name = "Indian River Flying Club, Inc"
arrow_make_and_model = "Piper PA28R-201"

csv_field_first_name = "first_name"
csv_field_last_name = "last_name"
csv_field_date = "date"
csv_field_hours = "hours"
csv_field_make_and_model = "make_and_model"
csv_field_date_parsed = "new_date"

# ################
# Functions
# ################
def update_checkout_date(last_name, first_name, email, groups, checkout): 
    new_checkout_date_and_expiration = (None, None)
    print ("Checking for Arrow hours for %s, %s, %s" % (last_name, first_name, email))
    #print ("   %s" % (json.dumps(checkout, indent=4)))

    if ( checkout['checkout_expires'] != "Never" ):
        print ("   Checking for recent flight billing")
        hours = 0
        for row in csv_data: 
            if ( row[csv_field_first_name].lower() == first_name.lower() and
                    row[csv_field_last_name].lower() == last_name.lower() and 
                    row[csv_field_date_parsed] > _180_days_ago):
                hours += float(row[csv_field_hours])
                if (hours >= 3):
                    print ("    New checkout date: %s" % row[csv_field_date])
                    new_checkout_date_and_expiration = (row[csv_field_date_parsed], days_valid)
                    break
        if (hours < 3):
            print ("    3 hours not found in the last %s days" % days_valid)
    else:
        print ("    User set to never expire")

    return new_checkout_date_and_expiration

# ################
# Main
# ################
parser = argparse.ArgumentParser(description='Updates IRFC Arrow checkout dates based on recent flight data')
parser.add_argument('--username', 
                    dest='username',
                    required = (username == None), 
                    help = "FlightCircle Username")
parser.add_argument('--password', 
                    dest = 'get_pass', 
                    action='store_true', 
                    required = (password == None), 
                    help = "Prompts for a FligthCircle Password")
parser.add_argument('--csv-file', 
                    dest='hours_file', 
                    required = True, 
                    help = "CSV Containing billed hours")
args = parser.parse_args()

if (args.username is not None):
    username = args.username

if (args.get_pass):
    password = getpass.getpass("FlightCircle Password: ")

if (not os.path.exists(args.hours_file)):
    print ("Hours file not found: %s" % args.hours_file)
    sys.exit(1)

# Read the hours data
with open(args.hours_file, "r") as csvfile:
    csv_data = list(csv.DictReader(csvfile))

for row in csv_data:
    row['new_date'] = datetime.datetime.strptime(row[csv_field_date], "%m/%d/%Y")
csv_data = sorted(csv_data, key = lambda i: i['new_date'], reverse=True) 

fs = flight_circle.FlightCircle(username, password)
fbo_id = fs.get_fbo_id_by_name(fbo_name)

fs.update_checkout_dates(fbo_id, arrow_make_and_model, update_checkout_date)

