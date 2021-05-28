import boto3
import os
import base64
import botocore
import datetime
import zipfile
import json
import time
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
 

#ECS##
ecs = boto3.client('ecs')
cluster_name = os.environ['cluster_name']

##_ECMWF WF_##
def launch(event, context):
    response = ecs.run_task(
        cluster=os.environ['cluster_name'],
        count=1,
        #group= os.environ['task_definition'],
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [os.environ['subnets']],
                'securityGroups': [os.environ['SecurityGroups']],
                'assignPublicIp': 'ENABLED'
            }
    },
    overrides={
        'containerOverrides': [
            {
                'name': os.environ['container_name'],
                'environment': [
                    {
                        'name': 'LD_LIBRARY_PATH',
                        'value': os.environ['LD_LIBRARY_PATH']
                    },
                    {
                        'name': 'username',
                        'value': os.environ['username']
                    },
                    {
                        'name': 'password',
                        'value': os.environ['password']
                    },
                    {
                        'name': 'login_url',
                        'value': os.environ['login_url']
                    },
                    {
                        'name': 'filesupdate_table',
                        'value': os.environ['filesupdate_table']
                    },
                    {
                        'name': 'BUCKET_NAME',
                        'value': os.environ['BUCKET_NAME']
                    },
                    {
                        'name': 'FIRST_BUCKET_PATH',
                        'value': os.environ['FIRST_BUCKET_PATH']
                    },
                    {
                        'name': 'SECOND_BUCKET_PATH',
                        'value': os.environ['SECOND_BUCKET_PATH']
                    },
                    {
                        'name': 'AWS_DEFAULT_REGION',
                        'value': os.environ['AWS_DEFAULT_REGION']
                    },
                ],
            },
        ]
    },
        platformVersion='1.4.0',
        taskDefinition= os.environ['task_definition']
    )
    return str(response)