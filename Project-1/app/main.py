from fastapi import FastAPI, HTTPException, Response, Depends, status
from sqlalchemy.orm import Session
from . import models 
from .database import engine, get_db
from . import schemas

models.Base.metadata.create_all(bind=engine)
app=FastAPI()

my_post=[{"title":"title 1","content":"content 1","id":1},
         {"title":"title 2","content":"content 2","id":2}
         ]  
  
@app.get("/")
async def root():
    return{"message":"API is running."}

@app.get("/posts",response_model=list[schemas.ResponseBase])
async def get_posts(db: Session =Depends(get_db)):
    # cursor.execute(""" SELECT * FROM posts""")
    # posts=cursor.fetchall()
    posts=db.query(models.Post).all() # accessing the class Post inside models.py and fetching all the records from the table posts
    return posts

@app.post("/posts",status_code=status.HTTP_201_CREATED,response_model=schemas.ResponseBase)
async def create_post(data: schemas.CreatePost,db: Session=Depends(get_db)):   
    # cursor.execute("""INSERT INTO posts(title,content,published) values (%s,%s,%s) RETURNING  * """,
    #                (data.title,data.content,data.published))
    # new_post=cursor.fetchone()
    # conn.commit()
    new_post=models.Post(title=data.title,content=data.content,published=data.published)# Just creating an instance of the class Post and passing the values to it
    db.add(new_post) # adding the new_post to the database session
    db.commit()# commit the changes
    db.refresh(new_post) # functioning as RETURNING * in SQL,it basically gets the commited posts back to new_post variable.
 
    
    # It is highly inefficient to reference each column and get each value by writing code
    # like 'title=data.title' for every column, so we can use **data.dict() to unpack the data 
    # and pass it to the Post class constructor, which will automatically map the fields.
    
    # new_post=models.Post(**data.dict()) # data.dict will convert the input into dictionary and ** will unpack that dic ,this will unpack the data and pass it to the Post class constructor
    # db.add(new_post) # adding the new_post to the database session
    return new_post
 
@app.get("/posts/latest",response_model=schemas.ResponseBase)
async def get_latest_post(db: Session = Depends(get_db)):
    post=db.query(models.Post).order_by(models.Post.created_at.desc()).first() # .order_by is used to sort the records based on created_at column in descending order and .first is used to get the first record from the sorted records
    if not post:
        raise HTTPException(status_code=404, detail="No posts found")
    return post
        
@app.get("/posts/{id}",response_model=schemas.ResponseBase)
async def get_post(id: int,db: Session=Depends(get_db)):
    post = db.query(models.Post).filter(models.Post.id == id).first() # .first is used to match the id and get the first record that matches the condition, to prevent code from looking for the id again after finding itonce
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")  
    return post
  
@app.delete("/posts/{id}",status_code=204)
async def delete_post(id: int,db: Session =Depends(get_db)):
    post=db.query(models.Post).filter(models.Post.id==id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    
@app.put("/posts/{id}",response_model=schemas.ResponseBase)
async def update_post(id: int,data: schemas.UpdatePost,db : Session =Depends(get_db) ):
    update_post= db.query(models.Post).filter(models.Post.id==id).update(data.model_dump(),synchronize_session=False)
    # .filter(...) finds the row(s) matching the id
# .update(dict) takes a dictionary directly (no ** needed) and builds 
#   the SQL SET title=..., content=..., published=... from it
# synchronize_session=False tells SQLAlchemy not to bother syncing this 
#   change with any Post objects already loaded in memory in this session 
#   (faster, since we don't need that here)
    print(update_post)
    
    if not update_post:
        raise HTTPException(status_code=404,detail="Post not found")
    db.commit()
    update_post=db.query(models.Post).filter(models.Post.id==id).first()# refetches the updated post , withoiut it the response body would output 1 on a successful update
    return update_post
    
            