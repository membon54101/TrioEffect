import json
import boto3
import psycopg2
import json
    


def lambda_handler(event, context):
    # Core Lambda Function
    client = boto3.client('secretsmanager')
    
    response = client.get_secret_value(
    SecretId= 'arn:aws:secretsmanager:us-east-1:917881085361:secret:AuroraPostgresConnInfoReadOnly-voq6SZ')
    database_secrets = json.loads(response['SecretString'])
    db_user_name, db_pw, db_host = database_secrets["username"], database_secrets["password"], database_secrets["host"]
    conn = psycopg2.connect(database='food', user=db_user_name, password=db_pw, host=db_host, port='5432')
    cursor = conn.cursor()
    
    query = "select * from public.{table_name}".format(table_name = event['table'])
    cursor.execute(query)
   
   
   # Getting the column names
    column_names = []
    for i in cursor.description: 
        column_names.append(i[0])
    
    # Getting the column values
    final_list = []
    ii = 0
    for row in cursor.fetchall():
        values = list(row)
        new_dict = {}
        for i in range(len(values)):
            new_dict[column_names[i]] = values[i]
        final_list.append(new_dict)
        ii += 1  
        
    final_list = json.dumps(final_list, default=str).encode('utf-8')
    return final_list
    
        
        

        
