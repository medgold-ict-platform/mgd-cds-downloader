from chalice import Chalice, Cron
import mechanize
import http.cookiejar as cookielib
import json
import numpy as np
import cdsapi
import boto3
import os
from botocore.exceptions import ClientError
from threading import Thread
from boto3.dynamodb.conditions import Attr 
from time import sleep
from decimal import Decimal
from datetime import date

app = Chalice(app_name='dev-medgold-download_files')
threads = []
parameters=[]
# Request variables
var_rep={"total_precipitation":"totprec" ,"minimum_2m_temperature_in_the_last_24_hours":"tmin2m" ,"10m_u_component_of_wind": "10u","10m_v_component_of_wind":"10v" ,"2m_dewpoint_temperature":"2d" ,"surface_solar_radiation_downwards":"ssrd" ,"maximum_2m_temperature_in_the_last_24_hours":"tmax2m" }
client = boto3.client('events')

vars = ['total_precipitation','minimum_2m_temperature_in_the_last_24_hours', 
'maximum_2m_temperature_in_the_last_24_hours', '10m_u_component_of_wind'
,'10m_v_component_of_wind', '2m_dewpoint_temperature', 'surface_solar_radiation_downwards']
#vars =['minimum_2m_temperature_in_the_last_24_hours']
pars = ['228'    , '52', '51', '165', '166', '56', '169']
#pars = ['52']

j_varpar= {'total_precipitation':'228', 
'minimum_2m_temperature_in_the_last_24_hours': '52',
'maximum_2m_temperature_in_the_last_24_hours': '51',
'10m_u_component_of_wind': '165',
'10m_v_component_of_wind': '166',
'2m_dewpoint_temperature': '56',
'surface_solar_radiation_downwards':'169'}

c = cdsapi.Client()
time_steps = np.arange(24,5161,24)
time_steps_char = [str(n) for n in time_steps] 
'/'.join(time_steps_char)
path = '/tmp/'
origin = 'ecmwf'
org='ecmf'
stream = 'mmsf'
system = '5'
format = 'grib'
dataset = 'seasonal-original-single-levels'
years = [x for x in range(2019, date.today().year+1)]
year = 0
var = ''
r_limit = 40
n_req = 0

##BOTO##
s3 = boto3.resource("s3")
s3Client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['filesupdate_table'])
BUCKET_NAME= os.environ['BUCKET_NAME']
bucket = s3.Bucket(BUCKET_NAME)
FIRST_BUCKET_PATH = os.environ['FIRST_BUCKET_PATH']

# Login #
username = os.environ['username']
password = os.environ['password']
login_url = os.environ['login_url']

#Run every 13th day of the month
@app.schedule(Cron(5, 12, 14, '*', '?', '*'))
def download_files(event):
    check(int(date.today().month))
    #priority_req()

#Run at 8am every WED
@app.schedule(Cron(0, 8, 1, '*', '?', '*'))
def check_pending_request(event):
    get_all_queued_requests()
    


def check(month):
    global n_req
    # get list of downloading file form cds website
    json_obj = get_jsonlist()
    #for year in years:
    year = date.today().year
    #if year != int(date.today().year) or month <= int(date.today().month):
    for var in vars:
        if n_req <= r_limit:
            try:
                # check if the specific request is scheduled
                response = table.scan(
                    FilterExpression = Attr('year').eq(year)&Attr('month').eq(month)&Attr('var').eq(var_rep[var])&Attr('dataset').eq(str(origin))
                )
                print(str(year)+ str(month) + str(var))
                item = response['Items']
                # if the request is not scheduled or is not in done status
                if len(item) is 0 or item[0]['state'] != 'done':
                    # create thread to send request
                    create_thread(year,var,month)
                    # update counter of requests
                    n_req = n_req + 1
                    parameters.append((year,var,month))
                    # create rule (or enable) on cloudwatch 
                    update_rule('mgd-cds-download-files-every_day','cron(0 12 * * ? *)','ENABLED', 'run every day after 13th day of the month until all files will be downloaded')
                    put_target('mgd-cds-download-files-every_day', os.environ['second_lambda_arn'])
                else:
                    # disable rule on cloudwatch
                    update_rule('mgd-cds-download-files-every_day','cron(0 12 * * ? *)','DISABLED', 'run every day after 13th day of the month until all files will be downloaded')
            except ClientError as e:
                print(e)
                pass
    start_threads()  
    threads = []

def update_rule(name, cron, state, description):
    response = client.put_rule(
        Name=name,
        ScheduleExpression=cron,
        State=state,
        Description=description,
    )

def put_target(rule, lambda_arn):
    response = client.put_targets(
        Rule=rule,
        Targets=[
            {
                'Arn': lambda_arn,
                'Id': rule,
            }
        ]    
    )


def sendrequest(year,var, month):
    param = j_varpar[var] + '.128'
    print('sendr')
    try:
        print(n_req)
        target = path + "ecmf_" + str(year) + str(month) + var_rep[var] + ".grib"
        print('+++ RETRIEVING ' + var_rep[var] + ' year:' + str(year) + ' month:' + str(month))

        response = c.retrieve(
            dataset,
            {
            'format':format,
            'originating_centre':origin,
            'variable':var,
            'year': str(year),
            'month':str(month),
            'day':'01',
            'leadtime_hour':time_steps_char,
            'area':[52,-13,29,38],
            'system': system
        }, target)
        
        json_obj = get_jsonlist()
        obj = find_obj(json_obj,year,var, month)
        upload_file(year,var, month)
        put_item(obj,year,var,month, 'done')
    except:
        raise


def get_jsonlist():
    cj = cookielib.CookieJar()
    br = mechanize.Browser()
    br.set_cookiejar(cj)
    br.open(login_url)
    br.select_form(nr=0)
    br.form['name'] = username
    br.form['pass'] = password
    br.submit()
    br.open('https://cds.climate.copernicus.eu/broker/api/v1/0/requests')

    obj = str(br.response().read().decode("utf-8"))
    print(obj)
    json_obj = json.loads(obj)
    return json_obj

def upload_file(year,var, month):
    target =  str(year) +'/'+ str(month) +'/'+ "ecmf_" + str(year) + str(month) + var_rep[var] + ".grib"
    name_of_file= "ecmf_" + str(year) + str(month) + var_rep[var] + ".grib"
    bucket.upload_file(path+name_of_file, FIRST_BUCKET_PATH + target)
    object = s3.Bucket(BUCKET_NAME).Object(FIRST_BUCKET_PATH + target)
    object.Acl().put(ACL='public-read')

def put_item(obj,year,var,month, state):
    try:
        month = obj['request']['specific']['month']
        var = var_rep[obj['request']['specific']['variable']]
        year = obj['request']['specific']['year']
        table.put_item(
            Item={
                'id': "ecmf_" + str(year) + str(month) + var,
                'dataset': origin,
                'month': int(month),
                'var': var,
                'year':int(year),
                'state': state
            }
        )
    except ClientError as e:
        raise

def find_obj(json_obj, year,var, month):
    obj = ''
    for el in json_obj:
        print(el)
        if el['request']['specific']['year'] == str(year) and el['request']['specific']['month'] == str(month) and el['request']['specific']['variable'] == var and el['request']['specific']['originating_centre'] == origin:
            obj = el
            break
    return obj 

def create_thread(year,var, month):
    print('creazione')
    global threads
    thread = Thread(target = sendrequest, args =(year,var,month,))
    threads.append(thread)
    print(len(threads))

def start_threads():
    i = 0
    print(parameters)
    for x in threads:
        x.start()
        json_obj = get_jsonlist()
        obj=find_obj(json_obj,parameters[i][0], parameters[i][1],parameters[i][2])
        print(obj)
        put_item(obj, parameters[i][0], parameters[i][1],parameters[i][2], obj['status']['state'])
        i = i + 1

    for x in threads:
        print('join')
        x.join()


def get_all_queued_requests():
    try:
        response = table.scan(
            FilterExpression = Attr('state').ne('done') 
        )
        inv_map = {v: k for k, v in var_rep.items()}
        items = response['Items']
        print(items)
        if len(items) is not 0:
            update_rule('mgd-cds-queued-requests','cron(0 12 * * ? *)','ENABLED', 'run every day after 1st day of the month until all queued requests will be done')
            put_target('mgd-cds-queued-requests', os.environ['first_lambda_arn'])
            if n_req < r_limit:
                for el in items:
                    global month
                    month = el['month']
                    year = el['year']
                    var = el['var']
                    variable = inv_map[var]
                    parameters.append((year,variable,month))
                    create_thread(year,variable, month)
            start_threads()
        else:
            update_rule('mgd-cds-queued-requests','cron(0 12 * * ? *)','DISABLED', 'run every day after 1st day of the month until all queued requests will be done')
    except ClientError as e:
        raise

# def priority_req():
#     for month in priority_month:
#         check(month) create_thread(year,var, month)