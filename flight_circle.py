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

from bs4 import BeautifulSoup
import datetime
import time
import json
import requests

class FlightCircle:
    """Class for interacting with the FlightCircle application"""
    __base_url__ = "https://www.flightcircle.com/v1/" # Trailing is required for login
    __fbos_url__ = "%sapi/associations" % __base_url__
    __users_url__ = "%sapi/customers" % __base_url__
    __default_headers__ = {'User-Agent': 'Indin River Flying Club Client (jon.vadney@gmail.com)',
                           'accept': 'application/json',
                           'referer': __base_url__,
                          }

    def __init__(self, username, password):
        """Initialize the object"""
        self.username = username
        self.password = password
        self.csrf_token = None
        self.user_data = None
        self.session = None

        self.__init_session__()

    def get_fbos(self):
        """Get a list of active FBO's"""
        # Get available associations
        payload = {"csrfToken": self.csrf_token,
                   "fields": "UserID",
                   "q": self.user_data['ID']
                  }
        print ("Connecting to %s" % FlightCircle.__fbos_url__)
        r = self.session.get(FlightCircle.__fbos_url__, 
                             headers=FlightCircle.__default_headers__, 
                             params = payload)
        if (r.status_code != 200):
            print (r)
            print (r.text)
            raise Exception("Unable to get FBO List")
        associations = json.loads(r.text)

        return associations

    def get_fbo_id_by_name(self, fbo_name):
        """Gets the FBO by name"""
        fbos = self.get_fbos()
        for fbo in fbos:
            if (fbo["name"] == fbo_name):
                return fbo["FboID"]

        return None

    def get_users(self, fbo_id):
        """"Gets a list of users for an FBO"""
        payload = {"csrfToken": self.csrf_token,
                   "fields": "FboID",
                   "include_deleted": "0",
                   "include_photo": "0",
                   "q": fbo_id
                  }
        print ("Connecting to %s" % FlightCircle.__users_url__)
        r = self.session.get(FlightCircle.__users_url__, 
                             headers=FlightCircle.__default_headers__, 
                             params = payload)
        if (r.status_code != 200):
            print (r)
            print (r.text)
            raise Exception("Unable to get User List")
        customers = json.loads(r.text)

        return customers

    def get_users_with_checkout(self, fbo_id, make_and_model):
        """Gets a list of customers checked out in a given make & model"""
        selected_users = []
        users = self.get_users(fbo_id)
        for user in users: 
            if ('aircraft_checkouts' in user and user["aircraft_checkouts"] != None):
                checkouts = json.loads(user["aircraft_checkouts"])
                for checkout in checkouts:
                    if (checkout["Make_Model"] == make_and_model):
                        selected_users.append(user)
        return selected_users

    def update_checkout_dates(self, fbo_id, make_and_model, get_new_checkout_date_and_expiration_func):
        """
        Function calls get_new_checkout_date_and_expiration_func for every user with a valid checkout 
        recorded for make & model. 

        Args: 
            fbo_id: 
            make_and_model: 
            get_new_checkout_date_and_expiration_func: A reference to a function to be called to 
                get a new checkout date and expiration days
                def func(last_name, first_name, email, groups, checkout) returns ((timestamp)checkoutdate, (int) days_valid)
        """
        users = self.get_users(fbo_id)
        for user in users:
            if ('aircraft_checkouts' in user and user["aircraft_checkouts"] != None):
                checkouts = json.loads(user["aircraft_checkouts"])
                for checkout in checkouts:
                    if (checkout["Make_Model"] == make_and_model):
                        groups = None
                        if ('groups' in user):
                            groups = user['groups']
                        (checkout_date, days_valid) = get_new_checkout_date_and_expiration_func(user['last_name'], 
                                                                                                user['first_name'], 
                                                                                                user['email'], 
                                                                                                groups, 
                                                                                                checkout)
                        if (checkout_date != None and days_valid != None):
                            #print ("Update checkout date")
                            url = "%s/%s" % (FlightCircle.__users_url__, user["CustomerID"])
                            params = {"csrfToken": self.csrf_token,
                                      "FboID": fbo_id
                                     }
                            checkout_date = checkout_date.replace(hour=0, minute=0, second=0, microsecond=0)
                            expires_date = checkout_date + datetime.timedelta(days=days_valid)
                            checkout["checkout_expires_specfic"] = str(days_valid)
                            checkout["checkout_date"] = int(checkout_date.timestamp())
                            checkout["checkout_expires_date"] = expires_date.strftime("%Y-%m-%d 00:00:00")
                            checkout["checkout_expires"] = "Specify"

                            formated_checkout = str(checkouts)
                            formated_checkout = formated_checkout.replace("'", '\\"').replace(': ', ':').replace(', ', ',')
                            payload = "{\"aircraft_checkouts\":\"%s\"}" % (formated_checkout)
                            #print (url)
                            #print (params)
                            #print (payload)
                            r = self.session.put(url, 
                                                 headers=FlightCircle.__default_headers__, 
                                                 params = params, 
                                                 data = str(payload))
                            json_result = json.loads(r.text)
                            if ('status' in json_result and json_result['status'] != 200):
                                raise Exception("Unable to update checkout for %s %s" % (user['last_name'],user['first_name']))
                            if (len(json_result) != 1): 
                                raise Exception("Unable to update checkout for %s %s" % (user['last_name'],user['first_name']))
                            

    def __init_session__(self):
        """Init FlightCircle Session"""
        # Init Requests Session
        self.session = requests.Session()
        # Get the csrf_token
        r = self.session.get(FlightCircle.__base_url__, 
                             headers=FlightCircle.__default_headers__)
        soup = BeautifulSoup(r.text, features="html.parser")
        self.csrf_token = soup.find(id="csrf_token").get("value")

        if (self.csrf_token is None or self.csrf_token == ""):
            raise Exception("Unable to obtain initial csrf_token")
  
        # Login
        payload = {'email': self.username,
                   'password': self.password,
                   'csrf_token': self.csrf_token,
                  }
        r = self.session.post(FlightCircle.__base_url__, 
                              headers=FlightCircle.__default_headers__, 
                              data = payload)
        soup = BeautifulSoup(r.text, features="html.parser")
        script_data = soup.find("script")
        if (script_data != None and script_data != ""):
            for line in str(script_data).splitlines():
                if ("RB.User" in line):
                    self.user_data = json.loads(line.replace("RB.User = RB.User || ", '')[:-1])
        else:
            raise Exception("Login Failed")

        if (self.user_data is None):
            raise Exception("Login Failed")
