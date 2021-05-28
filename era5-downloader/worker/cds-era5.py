from botocore.exceptions import ClientError
from threading import Thread
from boto3.dynamodb.conditions import Attr 
from time import sleep
from decimal import Decimal
from datetime import date
import mechanize
import http.cookiejar as cookielib
import json
import cdsapi
import boto3
import os

threads = []
parameters=[]

command = {
    "t2m": {"commands":["dayavg", "daymin", "daymax"]},
    "wss": {"commands":["dayavg"],
        "expr":'wss=sqrt(v10*v10+u10*u10)',
        "name": "10 metre wind speed",
        "unit":"m s**-1",
        "to_merge":['10u', '10v']},
    "ssrd": {"commands":["daysum"]},
    "totprec": {"commands":["daysum"]},
    "rh": {"commands":["dayavg"],
        "expr":'rh=100*((0.611*exp(5423*((1/273) - (1/d2m))))/(0.611*exp(5423*((1/273) - (1/t2m)))));',
        "name": "2 metre relative humidity",
        "unit":" ",
        "to_merge":['d2m', 't2m']},
    "sp": {"commands":["dayavg"]}
}

compute =['rh', 'wss']

# Request variables
var_rep={"total_precipitation":"totprec" ,
        "10m_u_component_of_wind": "10u",
        "10m_v_component_of_wind":"10v",
        "2m_temperature":"t2m",
        "2m_dewpoint_temperature":"d2m",
        "surface_solar_radiation_downwards":"ssrd",
        "surface_pressure":"sp",
        "maximum_2m_temperature_since_previous_post_processing":"tmax2m",
        "minimum_2m_temperature_since_previous_post_processing":"tmin2m" }

client = boto3.client('events')
c = cdsapi.Client()

vars = ['total_precipitation','2m_temperature','2m_dewpoint_temperature','surface_solar_radiation_downwards','10m_u_component_of_wind','10m_v_component_of_wind','surface_pressure',"maximum_2m_temperature_since_previous_post_processing","minimum_2m_temperature_since_previous_post_processing"]
#vars = ['total_precipitation']

path = './files/'
origin = 'ecmf'
format = 'netcdf'
dataset = 'reanalysis-era5-single-levels'
#years = [x for x in range(1979, date.today().year+1)]
var = ''
prefix = 'ERA5'
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
SECOND_BUCKET_PATH = os.environ['SECOND_BUCKET_PATH']

# Login #
username = os.environ['username']
password = os.environ['password']
login_url = os.environ['login_url']

#Run every 13th day of the month
def download_files():
    check()

def check():
    global n_req
    # get list of downloading file form cds website
    json_obj = get_jsonlist()
    #for year in years:
    #year = date.today().year
    year = 2019
    #if year != int(date.today().year) or month <= int(date.today().month):
    for var in vars:
        if n_req <= r_limit:
            try:
                # check if the specific request is scheduled
                # response = table.scan(
                #     FilterExpression = Attr('year').eq(year)&Attr('var').eq(var_rep[var])&Attr('dataset').eq(str(prefix))
                # )
                print(str(year) + str(var))
                #item = response['Items']
                # if the request is not scheduled or is not in done status
                #if len(item) is 0 or item[0]['state'] != 'done':
                    # create thread to send request
                create_thread(year,var)
                    # update counter of requests
                n_req = n_req + 1
                parameters.append((year,var))
                    # create rule (or enable) on cloudwatch 
                    #update_rule('mgd-cds-download-files-every_day','cron(0 12 * * ? *)','ENABLED', 'run every day after 13th day of the month until all files will be downloaded')
                    #put_target('mgd-cds-download-files-every_day', os.environ['second_lambda_arn'])
                #else:
                    # disable rule on cloudwatch
                    #update_rule('mgd-cds-download-files-every_day','cron(0 12 * * ? *)','DISABLED', 'run every day after 13th day of the month until all files will be downloaded')
            except ClientError as e:
                print(e)
                pass
    start_threads()  

    for file in os.listdir(path):
        print(file)
        el = file.split('_')[1]
        el = el.replace(el[0:4], '').replace('.nc', '')
        #el = var_rep[el]
        print(el)
        for c in command[el]['commands']:
            copy = 'cdo -r -b 32 -f nc copy {} tmp.nc'.format(path+'/'+file)
            os.system(copy)
            name_of_file = file.replace('.nc', '_{}.nc').format(c)
            comcdo = "cdo -{} tmp.nc {}".format(c,path+'/'+name_of_file)
            os.system(comcdo)
            bucket.upload_file(path+'/'+name_of_file, SECOND_BUCKET_PATH+'/'+str(year)+'/'+name_of_file)
            object = s3.Bucket(BUCKET_NAME).Object(SECOND_BUCKET_PATH+'/'+str(year)+'/'+name_of_file)
            object.Acl().put(ACL='public-read')

    for el in compute:
        file1 = 'ERA5_{}{}.nc'.format(year, command[el]['to_merge'][0])
        file2 = 'ERA5_{}{}.nc'.format(year, command[el]['to_merge'][1])
        rh = "cdo -merge {} {} tmp.ALL.nc".format(path+'/'+file1, path+'/'+file2)
        os.system(rh)
        expr = "cdo -expr,{} tmp.ALL.nc tmp.{}.nc".format(command[el]['expr'], el)
        os.system(expr)
        ncatted = "ncatted -O -a long_name,rh,o,c,'{}' tmp.{}.nc ".format(command[el]['name'], el)
        os.system(ncatted)
        ncatted = "ncatted -O -a units,rh,o,c,\"{}\" tmp.{}.nc".format(command[el]['unit'], el)
        os.system(ncatted)
        c = command[el]['commands'][0]
        comcdo = "cdo -{} tmp.nc {}".format(c,path+'/ERA5_{}{}_{}.nc'.format(year,el, c)) 
        os.system(comcdo)
        rm = "rm -f tmp.*"
        os.system(rm)
        bucket.upload_file(path+'/ERA5_{}{}_{}.nc'.format(year,el, c), SECOND_BUCKET_PATH+'/'+str(year)+'/ERA5_{}{}_{}.nc'.format(year,el, c))
        object = s3.Bucket(BUCKET_NAME).Object(SECOND_BUCKET_PATH+'/{0}/ERA5_{0}{1}_{2}.nc'.format(year,el, c))
        object.Acl().put(ACL='public-read')

    threads = []

# def update_rule(name, cron, state, description):
#     response = client.put_rule(
#         Name=name,
#         ScheduleExpression=cron,
#         State=state,
#         Description=description,
#     )

# def put_target(rule, lambda_arn):
#     response = client.put_targets(
#         Rule=rule,
#         Targets=[
#             {
#                 'Arn': lambda_arn,
#                 'Id': rule,
#             }
#         ]    
#     )


def sendrequest(year,var):
    print('sendr')
    try:
        print(n_req)
        target = path + "ERA5_" + str(year) + var_rep[var] + ".nc"
        print('+++ RETRIEVING ' + target)

        response = c.retrieve(
            dataset,{
            'product_type':'reanalysis', 
            'format':format,
            'originating_centre': origin,
            'variable':var,
            'year':year,
            'month':['01','02','03','04','05','06','07','08','09','10','11','12'],
            'day':[
                '01','02','03',
                '04','05','06',
                '07','08','09',
                '10','11','12',
                '13','14','15',
                '16','17','18',
                '19','20','21',
                '22','23','24',
                '25','26','27',
                '28','29','30',
                '31'
            ],
            'time':[
                '00:00','01:00','02:00',
                '03:00','04:00','05:00',
                '06:00','07:00','08:00',
                '09:00','10:00','11:00',
                '12:00','13:00','14:00',
                '15:00','16:00','17:00',
                '18:00','19:00','20:00',
                '21:00','22:00','23:00'
            ],
            'area':[72,-22,27,45]
        }, target)
        
        json_obj = get_jsonlist()
        obj = find_obj(json_obj,year,var)
        upload_file(year,var)
        put_item(obj,year,var, 'done')
    except:
        raise


def get_jsonlist():
    cj = cookielib.CookieJar()
    br = mechanize.Browser()
    br.set_handle_robots(False)
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

def upload_file(year,var):
    target =  str(year) +'/'+ prefix + "_" + str(year) + var_rep[var] + ".nc"
    name_of_file=prefix + "_" + str(year) + var_rep[var] + ".nc"
    bucket.upload_file(path+name_of_file, FIRST_BUCKET_PATH + target)
    object = s3.Bucket(BUCKET_NAME).Object(FIRST_BUCKET_PATH + target)
    object.Acl().put(ACL='public-read')

def put_item(obj,year,var, state):
    try:
        var = var_rep[obj['request']['specific']['variable']]
        year = obj['request']['specific']['year']
        table.put_item(
            Item={
                'id': prefix + "_" + str(year) + var,
                'dataset': prefix,
                'var': var,
                'year':int(year),
                'state': state
            }
        )
    except ClientError as e:
        raise

def find_obj(json_obj, year,var):
    obj = ''
    for el in json_obj:
        if el['request']['specific']['year'] == year and el['request']['specific']['variable'] == var and el['request']['specific']['originating_centre'] == origin:
            obj = el
            break
    return obj 

def create_thread(year,var):
    print('creazione')
    global threads
    thread = Thread(target = sendrequest, args =(year,var,))
    threads.append(thread)
    print(len(threads))

def start_threads():
    i = 0
    obj = ''
    for x in threads:
        x.start()
        json_obj = get_jsonlist()
        obj=find_obj(json_obj,parameters[i][0], parameters[i][1])
        put_item(obj, parameters[i][0], parameters[i][1], obj['status']['state'])
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
        if len(items) is not 0:
            #update_rule('mgd-cds-queued-requests','cron(0 12 * * ? *)','ENABLED', 'run every day after 1st day of the month until all queued requests will be done')
            #put_target('mgd-cds-queued-requests', os.environ['first_lambda_arn'])
            if n_req < r_limit:
                for el in items:
                    year = el['year']
                    var = el['var']
                    variable = inv_map[var]
                    parameters.append((year,variable))
                    create_thread(year,variable)
            start_threads()
        # else:
            # update_rule('mgd-cds-queued-requests','cron(0 12 * * ? *)','DISABLED', 'run every day after 1st day of the month until all queued requests will be done')
    except ClientError as e:
        raise

if __name__ == "__main__":
    download_files()
