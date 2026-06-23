import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

# class Post(BaseModel):
#     title: str
#     content: str
#     published: bool=True
    
# class CreatePost(BaseModel):
#     title: str
#     content: str
#     published: bool=True    
    
# class UpdatePost(BaseModel):
#     title: str
#     content: str
#     published: bool     
    
    # for simple application like this, 
    # these multiple classes my be redundant, 
    # but as app gets complex these will have 
    # slighlty different request and response 
    # format based on action, so multiple schemas 
    # are used to keep the code clean and organized.
    
    
    # Or instead of makeing multiple classes just use inheritance
    
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
    model_config = ConfigDict(from_attributes=True)
   
    # by default Pydantic expects a dict like {"title": ..., "content": ...} as input
    # from_attributes=True tells Pydantic it is also allowed to read values directly
    # off an object's attributes instead, e.g. new_post.title, new_post.content
    # this is what lets us return a raw SQLAlchemy model instance (new_post) from the
    # route and have FastAPI correctly convert it into this response schema