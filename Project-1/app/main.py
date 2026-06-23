from random import randrange
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.params import Body
import psycopg2
from pydantic import BaseModel
app=FastAPI()
# define schema of Post,auto validates and send error messages as well

class Post(BaseModel):
    title: str
    content: str
    published: bool=True
    rating : Optional[int]=None
    
while True:    
    try:
        conn= psycopg2.connect(
            host='ep-twilight-sun-aouqcs81.c-2.ap-southeast-1.aws.neon.tech',
            database='neondb',
            user='neondb_owner',
            password='npg_K3yXJGaFt7xw',
            sslmode='require') 
        cursor=conn.cursor()
        print("Database connection was successful")
        break
    except Exception as error:
        print("Connecting to database failed")
        print("error: ", error)
          
    
my_post=[{"title":"title 1","content":"content 1","id":1},
         {"title":"title 2","content":"content 2","id":2}
         ]    
@app.get("/")
async def root():
    return{"message":"API is running."}

@app.get("/posts")
async def get_posts():
    cursor.execute(""" SELECT * FROM posts""")
    posts=cursor.fetchall()
    return{"post":posts}

@app.post("/posts")
async def create_post(data: Post,response: Response):
    cursor.execute("""INSERT INTO posts(title,content,published) values (%s,%s,%s) RETURNING  * """,
                   (data.title,data.content,data.published))
    new_post=cursor.fetchone()
    conn.commit()
    response.status_code = 201 
    return {"post":new_post}

def find_post(id):
    for p in my_post:
        if p["id"]==id:
            return p
 
 
@app.get("/posts/latest")
async def get_latest_post():
    return{"Latest post":my_post[len(my_post)-1 ]}    
        
@app.get("/posts/{id}")
async def get_post(id: int):
        
    cursor.execute("""SELECT * FROM posts WHERE id=(%s)  """,
                   (id,))
    post=cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    return{"post":post}
  
def find_index_post(id):
    for i ,p in enumerate(my_post):
        if p['id']==id:
            return i
            
@app.delete("/posts/{id}",status_code=204)
async def delete_post(id: int):
    
    cursor.execute(''' DELETE FROM  posts WHERE id=(%s) RETURNING *''',(id,))
    post=cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    conn.commit()
    
    
    
    
@app.put("/posts/{id}")
async def update_post(id: int,data: Post):
    cursor.execute('''UPDATE posts SET title=(%s), content=(%s), published=(%s) where id=(%s) RETURNING *''',
                   (data.title,data.content,data.published,id))
    update_post=cursor.fetchone()
    
    
    if not update_post:
        raise HTTPException(status_code=404,detail="Post not found")
    conn.commit()
    return{"post":update_post}
    
            