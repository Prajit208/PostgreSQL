from jose import JWTError, jwt
from datetime import datetime,timedelta,timezone
import os
from dotenv import load_dotenv 
load_dotenv()
# SECRET_KEY+ algorithm+ expiration time
SECRET_KEY=os.getenv('SECRET_KEY')

ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

def create_access_token(data: dict):
    to_encode=data.copy()# copy to not accidently manipulate original data
    expire=datetime.now(timezone.utc)+ timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)# sets expiry time starting from now
    to_encode.update({'exp':expire}) # adding another key value pair to dict
    
    encoded_jwt=jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)# takes a secret key, payload and algorithm to create a unique signature
    return encoded_jwt

# def verify_access_token():