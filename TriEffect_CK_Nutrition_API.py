import json
import boto3
import psycopg2
import json
#import simplejson as json

def lambda_handler(event, context):
    # TODO implement
    
    client = boto3.client('secretsmanager')

    response = client.get_secret_value(
    SecretId= 'arn:aws:secretsmanager:us-east-1:917881085361:secret:AuroraPostgresConnInfoReadOnly-voq6SZ')
    database_secrets = json.loads(response['SecretString'])
    db_user_name, db_pw, db_host = database_secrets["username"], database_secrets["password"], database_secrets["host"]
    conn = psycopg2.connect(database='food', user=db_user_name, password=db_pw, host=db_host, port='5432')
    cursor = conn.cursor()
    
    
    # Execute query
    ck_food_id = event['ck_food_id']
    cursor.execute("select json from public.ck_food where id=" + ck_food_id + "")
    result = cursor.fetchall()
    result = str(result[0]).replace('\\', '')
    result = result[2:-3]
    result = json.loads(result)
    
    return result

