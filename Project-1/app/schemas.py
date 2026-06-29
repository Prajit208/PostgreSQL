from datetime import datetime
from pydantic import BaseModel, ConfigDict,EmailStr, conint
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
      
    
class CreateUser(UserBase):
    password: str   

class UserOut(UserBase): # user response model
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    
class UserLogin(BaseModel):
    email: EmailStr
    password:str    
        
class PostBase(BaseModel):
    title: str
    content: str
    published: bool = True
   
class CreatePost(PostBase):
    pass

class UpdatePost(PostBase):
    pass    

class ResponseBase(PostBase):
    id : int
    created_at: datetime
    owner_id: int
    owner: UserOut
    model_config = ConfigDict(from_attributes=True)
   
    # by default Pydantic expects a dict like {"title": ..., "content": ...} as input
    # from_attributes=True tells Pydantic it is also allowed to read values directly
    # off an object's attributes instead, e.g. new_post.title, new_post.content
    # this is what lets us return a raw SQLAlchemy model instance (new_post) from the
    # route and have FastAPI correctly convert it into this response schema
class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    id: Optional[int]=None        
    
class Vote(BaseModel):
    post_id: int
    dir: conint(ge=0,le=1)    