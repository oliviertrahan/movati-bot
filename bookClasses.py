# coding: utf-8

from math import floor
from datetime import datetime, timedelta, time
import json
import re
from time import sleep
import os

import modal
dockerfile_image = modal.Image.from_dockerfile("Dockerfile")
stub = modal.Stub("movati-bot")

"""
utility classes
"""
from dataclasses import dataclass
if stub.is_inside():
    import requests
    import dataclass_wizard
    import pytz

    @dataclass
    class ClassBookingConfig:
        location_id: int
        class_name: str
        day_of_week: str
        start_time: time
        end_time: time

    @dataclass
    class UserClassBookingConfig:
        person_name: str
        account_email: str
        account_password: str
        class_bookings: list[ClassBookingConfig]

    class ClassCacheService(object):
        def __init__(self):
            self.data = {}
            self.expiration_data = {}

        def __setitem__(self, key, item):
            self.data[key] = item

        def get_expiration(self, key):
            return self.expiration_data.get(key)

        def set_expiration(self, key, datetime):
            self.expiration_data[key] = datetime

        def __delitem__(self, key): 
            del self.data[key]
            del self.expiration_data[key]

        def __getitem__(self, key):
            expiration = self.expiration_data.get(key)
            #hardcoding timezone for now
            if (expiration is not None and expiration < datetime.now(tz=pytz.timezone('America/Toronto'))): 
                self.__delitem__(key)
            return self.data.get(key)



    GXP_SECURITY_COOKIE = 'gxp_sec_cookie'
    PHP_SESSION_ID = 'PHPSESSID'
    class_values = [
        'date',
        'time_range',
        'name',
        'description',
        'studio',
        'category',
        'instructor',
        'instructor_id',
        'location',
        'details',
        'unknown1',
        'unknown2',
        'image_name',
        'image_link',
        'class_id',
        'reserved'
    ]    

    """
    config variables
    """
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    movati_account_id = 577
    movati_trainyards_location_id = 2308

    movati_trainyards_timezone = pytz.timezone('America/Toronto')

    accounts_to_book = [
        UserClassBookingConfig('Olivier', os.environ.get('OLIVIER_EMAIL'), os.environ.get('OLIVIER_PASSWORD'), [
            ClassBookingConfig(movati_trainyards_location_id, 'Rhythm & Beats (E)', 'Tuesday', time(17, 30), time(23, 59)),
            ClassBookingConfig(movati_trainyards_location_id, 'Rhythm & Beats (E)', 'Thursday', time(17, 30), time(23, 59)),
            ClassBookingConfig(movati_trainyards_location_id, 'Anti-Gravity® Fitness 1 (E)', 'Sunday', time(10, 00), time(23, 59)),
        ]),
        UserClassBookingConfig('Valerie', os.environ.get('VALERIE_EMAIL'), os.environ.get('VALERIE_PASSWORD'), [
            ClassBookingConfig(movati_trainyards_location_id, 'Rhythm & Beats (E)', 'Tuesday', time(17, 30), time(23, 59)),
            ClassBookingConfig(movati_trainyards_location_id, 'Rhythm & Beats (E)', 'Thursday', time(17, 30), time(23, 59)),
            ClassBookingConfig(movati_trainyards_location_id, 'Anti-Gravity® Fitness 1 (E)', 'Sunday', time(10, 00), time(23, 59)),
            #ClassBookingConfig(movati_trainyards_location_id, 'Bungee Workout™ (E)', 'Sunday', time(10, 00), time(23, 59)),
        ])
    ]
    start = floor(datetime.now().timestamp()) #start time to get schedule
    end = floor((datetime.now() + timedelta(days=7)).timestamp()) #end time to get schedule
    class_want_to_book = ClassCacheService()

    # Get the list of classes to book at each particular location
    class_configs_per_location = {}
    for user_to_book in accounts_to_book:
        for booking_config in user_to_book.class_bookings:
            class_configs_per_location.setdefault(booking_config.location_id, [])
            class_configs_per_location[booking_config.location_id].append((user_to_book.person_name, user_to_book.account_email, user_to_book.account_password, booking_config))

    """
    logic
    """
    valid_days_to_book = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    def handle_incorrect_response(url, response):
        if not response.ok:
            print("status code: ", response.status_code)
            print("response: ", response.text)
            raise Exception(f"Failed to run request: {url}")


    def parse_class_start_time(time_range_string):
        # Define the regex pattern to match the time string
        pattern = r'^(\d{1,2})\:(\d{2})(a|p)m-.*'

        # Search for the pattern in the string and extract the hour, minute and meridian
        match = re.search(pattern, time_range_string)
        if match is None:
            raise Exception(f'could not parse start time from \"{time_range_string}\"')
        hour = int(match.group(1))
        minutes = int(match.group(2))
        meridian = match.group(3)

        # Convert the hour to 24-hour format if necessary
        if meridian == 'p' and hour != 12:
            hour += 12

        return time(hour, minutes)

    def is_valid_time(class_time, time_start, time_end):
        return class_time >= time_start and class_time <= time_end

    def get_valid_day_of_week(date_string):
        match = re.search(rf'({"|".join(valid_days_to_book)})', date_string)
        return match.group(1) if match is not None else None

    def get_class_state(class_details):
        match = re.search(r'textmsg="([^"]+)"', class_details)
        state = None
        spots_available = 0
        can_start_booking_on = None
        if match is not None:
            state = match.group(1) 
            match = re.search(r'^(\d+) SPOTS? LEFT$', state)
            spots_available = int(match.group(1)) if match is not None else 0
            match = re.search(r'data-info="([^"]*)"', class_details)
            if match is None:
                raise Exception(f'could not get data-info from \"{class_details}\"')
            elif match.group(1) == 'past':
                return state, 0, can_start_booking_on
            
            #if not in the past, then we can start booking on the start date
            match = re.search(r'start-info="(\d{2})/(\d{2})/(\d{4}) at (\d{1,2})\:(\d{2})(a|p)m"', class_details)
            if match is None:
                return state, spots_available, None
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))
            hour = int(match.group(4))
            minutes = int(match.group(5))
            meridian = match.group(6)
            if meridian == 'p' and hour != 12:
                hour += 12
            can_start_booking_on = datetime(year, month, day, hour, minutes, 0, 0, movati_trainyards_timezone)

        return state, spots_available, can_start_booking_on

    def get_class_booking_url(class_details):
        match = re.search(r'(https://groupexpro.com/gxp/reservations/schedule/index/\d+/\d{2}/\d{2}/\d{4})', class_details)
        return match.group(1) if match is not None else None

    def get_class_dict_key(class_data):
        return f"{class_data['date']}_{class_data['time_range']}_{class_data['name']}"

    def book_class(booking_url, user_email, user_password):
        #First load the page to get the php session cookie and gxp_sec_cookie
        booking_get_url = f'{booking_url}?e=1&type=new'
        response = requests.get(booking_get_url, allow_redirects=False, headers={
            'User-Agent': user_agent, 
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'en,fr-CA;q=0.9,fr;q=0.8',
            'accept-encoding': 'gzip, deflate, br',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': 'macOS',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1'
        })
        handle_incorrect_response(booking_get_url, response)

        gxp_sec_cookie = response.cookies.get(GXP_SECURITY_COOKIE)
        php_session_id = response.cookies.get(PHP_SESSION_ID)

        cookies_to_send = { GXP_SECURITY_COOKIE: gxp_sec_cookie, PHP_SESSION_ID: php_session_id }

        login_page = response.headers.get('location')
        if login_page is None:
            raise Exception('could not get login page from response')
        
        print('login page: ', login_page)
        response = requests.get(login_page, headers={'User-Agent': user_agent}, allow_redirects=False, cookies=cookies_to_send)
        handle_incorrect_response(login_page, response)
        print('login page get status code: ', response.status_code)

        # Now we login
        data = {
            'dest': login_page.replace('https://groupexpro.com/gxp/auth/login/', '').replace('?c=1&e=1&type=new', ''),
            'type': 'new',
            'e' : '1',
            'embeddedID': '',
            'gxp_sec_token': gxp_sec_cookie,
            'login': user_email,
            'password': user_password,
        }
        response = requests.post(login_page, allow_redirects=False, 
            headers={'User-Agent': user_agent, 'Content-Type': 'application/x-www-form-urlencoded'}, 
            cookies=cookies_to_send,
            data=data
        )
        handle_incorrect_response(login_page, response)

        gxp_sec_cookie = response.cookies.get(GXP_SECURITY_COOKIE)
        cookies_to_send = { GXP_SECURITY_COOKIE: gxp_sec_cookie, PHP_SESSION_ID: php_session_id }

        booking_redirect_page = response.headers.get('location')
        if booking_redirect_page is None:
            raise Exception('could not get booking redirect page from response')

        # Check the booking page now that we are logged in to see whether we already booked
        response = requests.get(booking_redirect_page, allow_redirects=False, headers={
                'User-Agent': user_agent
            }, 
            cookies=cookies_to_send
        )
        handle_incorrect_response(booking_get_url, response)
        #print(response.text)
        if 'You are currently signed up to attend this class' in response.text:      
            print('already booked')
            return False
        print('not booked')
        # Now we book once we are logged in
        data = {
            'gxp_sec_token': gxp_sec_cookie,
            'e' : '1',
            'type': 'new',
            'action': 'reserve',
            'submit': 'Reserve a Spot'
        }
        booking_response = requests.post(booking_url, allow_redirects=False, headers={
                'User-Agent': user_agent, 
                'Content-Type': 'application/x-www-form-urlencoded'
            }, 
            cookies=cookies_to_send,
            data=data
        )
        print('booking post response', booking_response.status_code)
        handle_incorrect_response(booking_get_url, booking_response)
        print('new booking')
        return True

    def book_classes():
        print("checking for classes on ", datetime.now(tz=movati_trainyards_timezone))
        for _, (location_id, user_bookings) in enumerate(class_configs_per_location.items()):
            print("checking for location: ", location_id)
            schedule_url = f"https://groupexpro.com/schedule/embed/json_schedule.php?schedule&instructor_id=true&format=jsonp&a={movati_account_id}&location={location_id}&category=6994,6995,6996,6998,6999,7000&studio=&class=&instructor=&start={start}&end={end}"

            response = requests.get(schedule_url, headers={'User-Agent': user_agent, 'Content-Type': 'application/json'}) 
            handle_incorrect_response(schedule_url, response)

            #Fix their shitty JSON
            response_json = response.text[1:-1] # remove the leading and trailing parentheses
            response_json = re.sub(r'\\\s', '', response_json) # replace single backslash with empty string
            response_json = re.sub(r'\\\'', '\'', response_json) # replace single backslash and quote with quote
            response_json = response_json.replace('	', '') # remove tabs

            try:
                schedule = json.loads(response_json, strict=False)
            except json.decoder.JSONDecodeError:
                with open('output.txt', 'w') as f:
                    f.write(response_json)
                raise Exception('could not parse json')
            booked_classes = []

            for movati_class_data in schedule['aaData']:
                class_data = {class_values[key]: value for key, value in enumerate(movati_class_data)}

                #For every person in the location, book the class if it is valid for that person
                for person_name, user_email, user_password, booking_config in user_bookings:
                    is_valid_class = class_data['name'] in booking_config.class_name
                    class_day_of_week = get_valid_day_of_week(class_data['date'])
                    class_time = parse_class_start_time(class_data['time_range'])
                    is_valid_class_time = is_valid_time(class_time, booking_config.start_time, booking_config.end_time)
                    class_state, spots_available, can_start_booking_on = get_class_state(class_data['details'])
                    

                    #Book class if it is valid and has unbooked spots
                    if (is_valid_class and class_day_of_week == booking_config.day_of_week and is_valid_class_time):
                        class_dict_key = get_class_dict_key(class_data)
                        #class_present = class_want_to_book[class_dict_key]
                        class_present = False
                        if class_present:
                            check_expiration = class_want_to_book.get_expiration(class_dict_key)
                            print(f"Found valid class for {person_name}: {class_data['name']} on {class_day_of_week} at {class_data['time_range']} which we have already tried/succeeded to book, but will only be available on {check_expiration}. Waiting.")
                            continue

                        #TODO: Handle the case where we can't book all users for the same class
                        if (spots_available > 1):

                            #Handle the scneario where we can't book yet
                            if (can_start_booking_on and datetime.now(tz=movati_trainyards_timezone) < can_start_booking_on):
                                print(f"Found valid class for {person_name}: {class_data['name']} on {class_day_of_week} at {class_data['time_range']} which is not yet available to book. Waiting to book until {can_start_booking_on}.")
                                continue

                            #get booking URL to book
                            print(f"Found valid class for {person_name}: {class_data['name']} on {class_day_of_week} at {class_data['time_range']} which is not fully booked. Booking now...")
                            booking_url = get_class_booking_url(class_data['details'])
                            if not booking_url:
                                raise Exception("Error while pars ing booking url")
                            
                            booked = book_class(booking_url, user_email, user_password) #TODO: handle case where different accounts have different states

                            #Track we don't want to try to book this class again for a while to not spam the login endpoint
                            class_want_to_book[class_dict_key] = True
                            class_want_to_book.set_expiration(class_dict_key, datetime.now(tz=movati_trainyards_timezone) + timedelta(hours=3))
                            booked_classes.append((class_data['name'], class_data['time_range'], class_day_of_week, person_name, booked))
                        else:
                            print(f"Found valid class for {person_name}: {class_data['name']} on {class_day_of_week} at {class_data['time_range']} with state \"{class_state}\". Skipping...")
                    else:
                        pass
                        #print(f"Found invalid class for {person_name}: {class_data['name']} on {class_day_of_week} at {class_data['time_range']}. Skipping...")
                        
            print(f"Found {len(booked_classes)} classes to book for location {movati_trainyards_location_id}")
            for class_name, class_time, class_day_of_week, person_name, booked in booked_classes:
                if booked:
                    print(f"Booked {class_name} at {class_time} on {class_day_of_week} for {person_name}!")
                else:
                    print(f"Wanted to book {class_name} at {class_time} on {class_day_of_week} for {person_name}, but it was already done!")

#run every minute
@stub.function(image=dockerfile_image, schedule=modal.Cron("* * * * *"), secret=modal.Secret.from_name("movati-creds"))
def cronBookClasses():
    book_classes()

@stub.local_entrypoint
def main():
    cronBookClasses.call()