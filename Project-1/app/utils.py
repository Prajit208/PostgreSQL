from passlib.context import CryptContext

pwd_context=CryptContext(schemes=['bcrypt'],deprecated='auto')
# hashing the password
def hash(password: str):
    return pwd_context.hash(password)
# a function for comparing inputed password with hashed and saved password in database
def verify(plain_password: str,hashed_password: str):
    return pwd_context.verify(plain_password,hashed_password)# returns true if password match
    