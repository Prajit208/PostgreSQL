from  fastapi import APIRouter,HTTPException,Depends,status
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models, schemas,oauth2
from ..database import get_db

router=APIRouter(prefix='/posts',tags=['Posts'])

@router.get("/",response_model=list[schemas.PostOut])
async def get_posts(db: Session =Depends(get_db),
                    current_user= Depends(oauth2.get_current_user),
                    limit: int=10,skip: int = 0,
                    search: Optional[str]= ""):
    
    # posts=db.query(models.Post).filter(models.Post.title.contains(search)).limit(limit).offset(skip).all() # accessing the class Post inside models.py and fetching all the records from the table posts
    # left outer join
    results=db.query(models.Post,func.count(models.Vote.post_id).label("Votes")).join(
        models.Vote,models.Vote.post_id==models.Post.id,isouter=True).group_by(models.Post.id).filter(models.Post.title.contains(search)).limit(limit).offset(skip).all()
    if not results:
        raise HTTPException(status_code=404,detail='No posts found')
    return results

# add a dependency to see if user is logged in before creating a post
@router.post("/",status_code=status.HTTP_201_CREATED,response_model=schemas.ResponseBase)
async def create_post(data: schemas.CreatePost,db: Session=Depends(get_db),current_user= Depends(oauth2.get_current_user)):   

    new_post=models.Post(owner_id=current_user.id,** data.model_dump())# Just creating an instance of the class Post and passing the values to it
    db.add(new_post) # adding the new_post to the database session
    db.commit()# commit the changes
    db.refresh(new_post) # functioning as RETURNING * in SQL,it basically gets the commited posts back to new_post variable.
 
    # It is highly inefficient to reference each column and get each value by writing code
    # like 'title=data.title' for every column, so we can use **data.dict() to unpack the data 
    # and pass it to the Post class constructor, which will automatically map the fields.
    
    # new_post=models.Post(**data.dict()) # data.dict will convert the input into dictionary and ** will unpack that dic ,this will unpack the data and pass it to the Post class constructor
    # db.add(new_post) # adding the new_post to the database session
    return new_post
 
@router.get("/latest",response_model=schemas.ResponseBase)
async def get_latest_post(db: Session = Depends(get_db),current_user= Depends(oauth2.get_current_user)):
    post=db.query(models.Post).order_by(models.Post.created_at.desc()).first() # .order_by is used to sort the records based on created_at column in descending order and .first is used to get the first record from the sorted records
    if not post:
        raise HTTPException(status_code=404, detail="No posts found")
    return post
        
@router.get("/{id}",response_model=schemas.PostOut)
async def get_post(id: int,db: Session=Depends(get_db),current_user= Depends(oauth2.get_current_user)):
    # post = db.query(models.Post).filter(models.Post.id == id).first() # .first is used to match the id and get the first record that matches the condition, to prevent code from looking for the id again after finding itonce
    post=db.query(models.Post,func.count(models.Vote.post_id).label("Votes")).join(
        models.Vote,models.Vote.post_id==models.Post.id,isouter=True).group_by(models.Post.id).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")  
    return post
  
@router.delete("/{id}",status_code=204)
async def delete_post(id: int,db: Session =Depends(get_db),current_user = Depends(oauth2.get_current_user)):
    post=db.query(models.Post).filter(models.Post.id==id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Forbidden")
    db.delete(post)
    db.commit()
    
@router.put("/{id}",response_model=schemas.ResponseBase)
async def update_post(id: int,data: schemas.UpdatePost,db : Session =Depends(get_db),current_user = Depends(oauth2.get_current_user)):
    update_post= db.query(models.Post).filter(models.Post.id==id).update(data.model_dump(),synchronize_session=False)
    # .filter(...) finds the row(s) matching the id
# .update(dict) takes a dictionary directly (no ** needed) and builds 
#   the SQL SET title=..., content=..., published=... from it
# synchronize_session=False tells SQLAlchemy not to bother syncing this 
#   change with any Post objects already loaded in memory in this session 
#   (faster, since we don't need that here)  
    if not update_post:
        raise HTTPException(status_code=404,detail="Post not found")
    if update_post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Forbidden")
    db.commit()
    update_post=db.query(models.Post).filter(models.Post.id==id).first()# refetches the updated post , withoiut it the response body would output 1 on a successful update
    return update_post
    
            