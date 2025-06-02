import json
import boto3
import psycopg2
import uuid
import jose
from jose import jwt
from pypika import Query, Table, Field
from jose import jws

def lambda_handler(event, context):
    
    # Core Lambda Function
    client = boto3.client('secretsmanager')

    response = client.get_secret_value(
    SecretId= 'arn:aws:secretsmanager:us-east-1:917881085361:secret:AuroraPostgresConnInfoReadOnly-voq6SZ')
    database_secrets = json.loads(response['SecretString'])
    db_user_name, db_pw, db_host = database_secrets["username"], database_secrets["password"], database_secrets["host"]
    conn = psycopg2.connect(database='food', user=db_user_name, password=db_pw, host=db_host, port='5432')
    cursor = conn.cursor()
    
    
    # Function to read and return user table
    def read(event, one=False):
        # Function to return all of the values in a give SQLServer table 
        def get_data_to_table(query):
            cursor.execute(query)
            # Getting the column names
            column_names = []
            for i in cursor.description: 
                column_names.append(i[0])
            final_dict = []
            ii = 0
            for row in cursor.fetchall():
                values = list(row)
                new_dict = {}
                for i in range(len(values)):
                    new_dict[column_names[i]] = values[i]
                    #print(new_dict)
                final_dict.append(new_dict)
                ii += 1  
            #final_dict = json.dumps(final_dict, default=str).encode('utf-8')
            return final_dict
            
        # Returns dictionary with single element for all values of that dimension
        def user_dimensions(user_dim_list, dimension_name):
            dim = ''
            final_dict = dict()
            for i in user_dim_list:
                for key, value in i.items():
                    dim = dim + value + ', '
            dim = dim[:-2]
            final_dict[dimension_name] = dim
            return final_dict
            
        user = """SELECT u.user_id, is_active_key, email, first_name, last_name, 
        street_address, street_address2, city, state, zip, insurance_id, created_at, 
        phone, u.last_updated_ts, height, dob, activity, weight, gender,
        date_part('year', age(dob)) as age
        FROM public."user" u
        where u.email = '""" + event['email'] + "'"
        
        # Get the user_id
        user_id_get = """SELECT user_id from public.user where email = '{email}'""".format(email = event['email'])
        cursor.execute(user_id_get)
        try:
            user_id = cursor.fetchall()[0][0]
        except:
            return {"message": "Could not find a user with that username.", "success": "False"}
        
        condition_description = """select c.condition_description  from public.user_conditions uc 
        join public.conditions c 
        on uc.condition_id = c.condition_id 
        where uc.user_id = '""" + user_id + """'
        """

        allergy_description = """select a.allergy_description  
            from public.user_allergies ua 
            join public.allergies a 
            on ua.allergy_id  = a.allergy_id 
            where ua.user_id = '""" + user_id + """'
        """

        diet_description = """select d.diet_description  from public.user_diets ud  
            join public.diets d 
            on ud.diet_id = d.diet_id
            where ud.user_id = '""" + user_id + """'
        """

        avoided_food_description = """select af.avoided_food_description  
            from public.user_avoided_foods ufa 
            join public.avoided_foods af 
            on ufa.avoided_food_id = af.avoided_food_id
            where ufa.user_id = '""" + user_id + """'
        """

        user_table = get_data_to_table(user)[0]
        condiiton_dict = user_dimensions(get_data_to_table(condition_description), 'conditions')
        diet_dict = user_dimensions(get_data_to_table(diet_description), 'diets')
        allergy_dict = user_dimensions(get_data_to_table(allergy_description), 'allergies')
        avoided_foods_dict = user_dimensions(get_data_to_table(avoided_food_description), 'avoided_foods')    
                
        user_table.update(condiiton_dict)
        user_table.update(diet_dict)
        user_table.update(allergy_dict)
        user_table.update(avoided_foods_dict)        
        
        final_dict = json.dumps(user_table, default=str).encode('utf-8')
        return final_dict
        
    # Function to reset the password
    def password_reset(event):
        
        # Get the user_id
        user_id_get = """SELECT user_id from public.user where email = '{email}'""".format(email = event['email'])
        cursor.execute(user_id_get)
        user_id = cursor.fetchall()[0][0]
        
        # Verify if the provided password is accurate
        
        password_verification_query = """SELECT case when password = crypt('{value}', password) then True else False
        end as verification
        FROM public.user_password where user_id = '{user_id}' and is_active_flag = True""".format(user_id = user_id, value = event['old_password'])
        cursor.execute(password_verification_query)
        verification_result = cursor.fetchall()[0][0]
        if verification_result == False:
            return {"message": "Provided password incorrect.", "success": "False"}
        else:
            # Updating of password 
            update_password_query = """UPDATE public.user_password set is_active_flag = False WHERE user_id = '{user_id}'; 
            INSERT INTO public.user_password (user_id, password , is_active_flag) VALUES ( '{user_id}' , crypt('{value}', gen_salt('bf')), True)""".format(value = event['new_password'], user_id = user_id)
            cursor.execute(update_password_query)
            conn.commit() 
            return {"message": "Password reset successfully", "success": "True"}

        
    # Function to write to the Aurora 
    def write(event):
        for i, ii in event.items():
            globals()[i] = "'" + ii + "'"
        user_id_uuid = uuid.uuid1()
        user_id_uuid_str = "'" + str(user_id_uuid) + "'"
        
        # Check is the user email is already in use. 
        existing_users = """select user_id from public.user where email = {email}""".format(email = email)
        cursor.execute(existing_users)
        conn.commit()
        existing_user_result = cursor.fetchall()
        if len(existing_user_result) > 0:
            return {"message": "The email entered is already is use. Please input a new one.", "success": "False"}

        # Insert into user table
        query = """INSERT INTO public.user
                (	user_id,	is_active_key ,	email,	first_name,	last_name,	street_address,	street_address2, city,
                   state,	zip ,	insurance_id,	created_at ,	phone,	last_updated_ts, height, dob, activity, weight, gender )
                VALUES({user_id}, True, {email}, {first_name}, {last_name}, {street_address}, {street_address2}, {city},
                {state}, {zip}, {insurance_id}, now(), {phone}, now(), {height}, {dob}, {activity}, {weight}, {gender})""".format(user_id = user_id_uuid_str, email =  email, 
                first_name = first_name, last_name = last_name, street_address = street_address, street_address2 = street_address2, 
                state = state, zip = zip, insurance_id = insurance_id, phone = phone, height = height, dob = dob, gender = gender,
                city = city, activity = activity, weight = weight)
        cursor.execute(query)
        conn.commit()
        
        query = """INSERT INTO public.user_password
                (user_id, password, is_active_flag)
                VALUES({user_id}, crypt({password}, gen_salt('bf')), True)""".format(user_id = user_id_uuid_str, password = password)
        cursor.execute(query)
        conn.commit()
        
        for dim_reference in event:
            l = {'allergies': ['allergy_description', 'allergy_id'], 'avoided_foods': ['avoided_food_description', 'avoided_food_id'], 'diets': ['diet_description', 'diet_id'], 'conditions': ['condition_description', 'condition_id']}
            if dim_reference in l.keys():
                dimension_list = event[dim_reference].split(',')
                for dimension in dimension_list:
                    query = "select " + l[dim_reference][1]+ " from public." + dim_reference + " where " + l[dim_reference][0] + " = '" + dimension.strip(' ') + "'"
                    cursor.execute(query)
                    id = cursor.fetchall()[0][0]
                    query2 = "INSERT INTO public.user_" + dim_reference + " (" + l[dim_reference][1] + ", last_updated_ts, user_id) values (" + str(id) + ", now(), " + user_id_uuid_str + ")"
                    cursor.execute(query2)
                    conn.commit()

        conn.commit()
        new_cart_id_dict = {"message": "New user created", "success": "True"}
        return new_cart_id_dict
    
    # Fuction to update user information    
    def update_user(event):
        attributes = ["email", "first_name", "last_name", "street_address", 
        "street_address2", "state", "zip", "insurance_id", "phone", 
        "weight", "height", "dob", "activity", "city", "gender"]
        
        #  Defining the user_id and the changing field
        user_id = "'" + str(event['user_id'] if event['user_id'] != '' else 'null') + "'"
        for i, ii in event.items():
            globals()[i] = "'" + ii + "'"
        
        # Update basic user attributes    
        for i in list(globals()):
            if i in attributes:
                query = """UPDATE public.user SET {field} = {value} where user_id = {user_id}""".format(field = i, value = globals()[i], user_id = user_id)
                cursor.execute(query)
                conn.commit()
                
        # Add new dimension ids to corresponting user dimension tables
        l = {'allergies': ['allergy_description', 'allergy_id'], 'avoided_foods': ['avoided_food_description', 'avoided_food_id'], 'diets': ['diet_description', 'diet_id'], 'conditions': ['condition_description', 'condition_id']}
        for dim in list(globals()):
            if dim in l.keys():
                dimension_list = event[dim].split(',')
                query_delete = """DELETE FROM public.user_{dim} where user_id = {user_id};""".format(dim = dim, user_id = user_id) 
                cursor.execute(query_delete)
                conn.commit()
                for indx, condition in enumerate(dimension_list):
                    condition = condition.strip(' ')
                    query_get_id = """SELECT {dim_id_name} from public.{dim} where {dim_description} = '{condition}';
                    """.format(dim = dim, user_id = user_id, dim_id_name = l[dim][1], dim_description = l[dim][0], condition = condition)
                    cursor.execute(query_get_id)
                    conn.commit()
                    dim_id = int(cursor.fetchall()[0][0])
                    query_add_new_id = """INSERT INTO public.user_{dim}(user_id, last_updated_ts, {dim_id_name}) 
                    values ({user_id}, now(), {dim_id});""".format(dim = dim, dim_id_name = l[dim][1], user_id = user_id, dim_id = dim_id)
                    cursor.execute(query_add_new_id)
                    conn.commit()
            
        return {'message': 'User information updated', "success": "True"}
    
    # Function for a user to login
    def login(event):
        
        apikey_response = client.get_secret_value(SecretId= 'arn:aws:secretsmanager:us-east-1:917881085361:secret:x-api-key-qtQaCq')
        apikey = json.loads(apikey_response['SecretString'])['x-pi-key']
        
        # Get the user_id from the email
        user_id_query = """SELECT user_id from public.user where email = '{email}'""".format(email = event['email'])
        cursor.execute(user_id_query)
        user_id = cursor.fetchall()[0][0]
        
        # Check to see if a lockout is in order
        lockout_query = """with logins as (
        select *
        from public.user_logins 
        where user_id = '{user_id}'
        order by attempt_timestamp desc limit 5),
        
        min_diff as (
        select extract(epoch from max(attempt_timestamp) - min(attempt_timestamp)) / 60  as difference_minutes
        from logins),
        
        success as (
        select case when True in (select distinct login_successful from logins) then True
        else False end as successfull_login),
        
        last_time as (select max(attempt_timestamp ) as last_login from logins)
        
        select 
        case when successfull_login =  False 
        and difference_minutes <= 5 
        and (extract(epoch from now() - last_login) / 60) < 5
        then True else false end as lockout
        from success
        join min_diff 
        on 1 = 1
        join last_time
        on 1= 1""".format(user_id = user_id)
        cursor.execute(lockout_query)
        lockout = cursor.fetchall()[0][0]
        print(lockout)
        if lockout == True:
            print('F')
            return {"message": "Too many failed login attempts. Account temporarily frozen.", "success": "False", "email": event['email']}
        
        # Execute query to check password
        password_verification_query = """SELECT case when password = crypt('{value}', password) then True else False
        end as verification
        FROM public.user_password where user_id = '{user_id}' and is_active_flag = True""".format(user_id = user_id, value = event['password'])
        cursor.execute(password_verification_query)
        verification_result = cursor.fetchall()[0][0]
        
        if verification_result == True:
            cursor.execute("""insert into public.user_logins (user_id, attempt_timestamp, login_successful) 
            values ('{usid}', now(), True)""".format(usid = user_id))
            conn.commit() 
            token = jwt.encode({'user': event['email']}, '310ec267-937a-4d32-a5b4-b9ce0f211722', algorithm='HS256')
            # , 'token': token
            return { "message": "Login successful.", "success": "True", "email": event['email'], "token": token}
        
        else:
            cursor.execute("""
            insert into public.user_logins (user_id, attempt_timestamp, login_successful) 
            values ('{user_id}', now(), False);
            delete from user_logins where user_id is null""".format(user_id = user_id))
            conn.commit()
            return {"message": "Invalid email or password.", "success": "False", "email": event['email']}
        

    
    # Execute Endpoint Functions
    if 'user-read' in event['endpoint']:
        response = read(event)
        return response
    elif 'user-create' in event['endpoint']:
        response = write(event)
        return response
    elif 'user-update' in event['endpoint']:
        response = update_user(event)
        return response
    elif 'user-authentication' in event['endpoint']:
        response = login(event)
        return response
    elif 'password_reset' in event['endpoint']:
        response = password_reset(event)
        return response
    else:
         return {'statusCode': 200,
        'result': 'NO ENDPOINT METHOD WAS TRIGGERED'}


