from jose import JWTError, jwt
from datetime import datetime,timedelta,timezone
from fastapi import Depends,status,HTTPException
from fastapi.security import OAuth2PasswordBearer
import os
from . import schemas
from dotenv import load_dotenv 
load_dotenv()
# SECRET_KEY+ algorithm+ expiration time
SECRET_KEY=os.getenv('SECRET_KEY')

ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
oauth2_scheme= OAuth2PasswordBearer(tokenUrl='login')# passing the login route

def create_access_token(data: dict):
    to_encode=data.copy()# copy to not accidently manipulate original data
    expire=datetime.now(timezone.utc)+ timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)# sets expiry time starting from now
    to_encode.update({'exp':expire}) # adding another key value pair to dict
    # algorithm 'singular' beacause the function only needs one to encode
    encoded_jwt=jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)# takes a secret key, payload and algorithm to create a unique signature
    return encoded_jwt

def verify_access_token(token:str,credentials_exception):
    # algorithms 'plural'because the function accepts a list of algorithms 
    try:
        payload= jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])# payload is dict(the original data/payload passed when creating user) that code decoded.
        id: str= payload.get('user_id') # pulls user_id into id
        if id is None:
            raise credentials_exception
        token_data=schemas.TokenData(id=id) # wraping the id into correct token schema
        return token_data
    except JWTError:
        raise credentials_exception
    
def get_current_user(token: str =Depends(oauth2_scheme)):
    credentials_exception= HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Could not validate credentials',headers={"WWW-Authenticate":"Bearer"})
    return verify_access_token(token,credentials_exception)