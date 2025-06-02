import json
import boto3
import psycopg2
import re
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
    Food = event['food']
    query = r"""select distinct id, name, servingunit, servingamount, cast(replace(regexp_replace(json, '\\', ''), '\', '') as varchar) nutrition
    from public.ck_food where lower(name) like lower('""" + Food + """%')"""
    
    r = []
    def query_res(query, one=False):   
        cursor.execute(query)
        for row in cursor.fetchall():
            for i, value in enumerate(row): 
                if cursor.description[i][0] ==  'nutrition':
                    try:
                        json_t = json.loads(value)
                        x = dict(((cursor.description[i][0], json_t), )) 
                    except ValueError:  # includes simplejson.decoder.JSONDecodeError
                        print('Decoding JSON has failed')
                else:
                    x = dict(((cursor.description[i][0], str(value).replace('\\', '')), )) 
                r.append(x)
                
        return (r[0] if r else None) if one else r
    
    result = query_res(query)
    
    ls = []
    for i in result:
        for key, json_item in i.items():
            if key == 'id':
                d = {}
                d['id'] = json_item
            if key == 'name':
                d['name'] = json_item
            if key == 'servingunit':
                d['servingunit'] = json_item
            if key == 'servingamount':
                d['servingamount'] = json_item
            if key == 'nutrition':
                for nkey, nitem in json_item.items():
                    if nkey == 'Calories':
                        d['Calories'] = nitem
                    if nkey == 'Serving':
                        d['Serving'] = nitem
                    if nkey == 'Unit':
                        d['Unit'] = nitem
                    if nkey == 'Facts':
                        d['Nutrition'] = nitem
                        
        ls.append(d)
        
    ck_result = [i for n, i in enumerate(ls) if i not in ls[n + 1:]]
        

        
    return  ck_result


