import json
import boto3
import psycopg2


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
    
    upc_id = event["upc"]
    query = """
    with qry1 as (select a.*, ubfn."name" , ubfn.amount_calc, ubfn.unit_name, ubfc.calories,
        count(*) over (partition by a.fdc_id) as row_n
        from public.usda_branded_food a
        join public.usda_branded_food_nutrition ubfn 
        on ubfn.fdc_id = a.fdc_id
        join public.usda_branded_food_calories ubfc
        on ubfc.fdc_id = a.fdc_id
        where gtin_upc like '""" + upc_id + """%'  ),
        
      qry2 as (select * from qry1 where row_n in (select max(row_n) from qry1) ),
      
      qry3 as (  
      select fdc_id as id, gtin_upc, description as "name", concat(serving_size, ' ', serving_size_unit) as servingunit, 1 as servingamount,
      concat('{"Calories":"',calories,'", "Serving":"1", "Unit":"', serving_size, ' ', serving_size_unit, '",') level1,
      concat('{"Name": "', a.name, '", "Amount": "', amount_calc, ' ', unit_name , '"}') as Facts
      from qry2 a),
      
      qry4 as (
      select distinct id, gtin_upc, name, servingunit , servingamount, level1, concat('"Facts": [',string_agg(Facts, ', '), ']}') AS json
      from qry3
      group by 1, 2, 3, 4, 5, 6 
      )
      
      select id, gtin_upc, name, servingunit , servingamount, concat(level1, json) as nutrition 
      from qry4
    """ 
    
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
    
    for item in result:
        for key, value in item.items():
            x = str(key)
            if key in ("id", "name", "servingamount", "servingunit", "gtin_upc"):
                result[0][x] = value
            else:
                #value = value + '}'  
                #res = json.loads(value)
                for k, v in value.items():
                    result[0][k] = v
        
    for i in range(3):
        result.pop(1)
        
    result[0]["Nutrition"] = result[0]["Facts"]
    del result[0]["Facts"]
    result.pop(1)
    result.pop(1)
    

    return  result 

