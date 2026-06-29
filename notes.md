# PostgreSQL and FastAPI Notes

## Data Types

| Data Type | Postgres | Python |
|---|---|---|
| Numeric | int, numeric(precision, scale) | int, float |
| Text | varchar(n), text | string |
| Boolean | boolean | boolean |
| Sequence | array | list |
| Date/Time | timestamp, timestamp with time zone | datetime |

Notes:
* `decimal` and `numeric` are the same type in Postgres, just two names for it.
* `varchar(n)` has a length limit, `text` does not. Most modern Postgres usage prefers `text` unless there is a real reason to cap length.
* `TIMESTAMP(timezone=True)` in SQLAlchemy maps to Postgres `timestamp with time zone`, which stores the timezone info instead of assuming a local time.

## Core SQL Concepts

### Primary Key
A column (or set of columns) that is unique and not null for every row. A table can only have one primary key. It is what the ORM uses by default to look up, update, or delete a specific row, for example `filter(models.Post.id == id)`.

### Foreign Key
A column in one table that references the primary key of another table. Postgres enforces that the value must already exist in the referenced table. This is the mechanism used to link records across tables, for example connecting a `posts` row to the `users` table to record who owns it.

### Constraints
* Unique constraint: no duplicate values allowed in that column.
* Not null constraint: no null values allowed in that column.
* Check constraint: restricts values to match a condition, for example `rating between 1 and 5`.
* Default constraint: if no value is given on insert, Postgres fills in a default automatically. Already used in the project: `server_default='TRUE'` on `published`, and `server_default=text('now()')` on `created_at`.

## Raw SQL with psycopg2 (before SQLAlchemy)

Used `cursor.execute()` with raw SQL strings and `%s` placeholders to prevent SQL injection, then `cursor.fetchone()` or `cursor.fetchall()` to get results back. Every change needed an explicit `conn.commit()` or it would not persist. Cleanup (`cursor.close()`, `conn.close()`) had to be managed manually.

Example pattern used for all five CRUD operations:
```python
cursor.execute("SELECT * FROM posts WHERE id = (%s)", (id,))
post = cursor.fetchone()
```

This works but every query is a separate hand written string, and there is no validation or object mapping. Each row comes back as a raw tuple, not a usable Python object.

## Moving to SQLAlchemy (ORM)

### Why
SQLAlchemy lets you describe tables as Python classes (models) and write queries using Python methods instead of SQL strings. It also returns full objects instead of raw tuples, so you can access fields like `post.title` directly.

### database.py setup
```python
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```
* `engine`: handles the actual connection to the database.
* `SessionLocal`: a factory that creates new database sessions on demand.
* `Base`: the parent class that all table models inherit from, so SQLAlchemy knows which classes map to tables.

### get_db() dependency
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
This is a generator, not a normal function. FastAPI runs it up to `yield`, hands the session to the route, waits for the route to finish, then resumes after `yield` to run the cleanup. The `finally` block guarantees the session closes even if the route raises an error. `Depends(get_db)` is what tells FastAPI to run this and inject the result into the route's `db` parameter, giving each request its own fresh session.

### Models (table definitions)
```python
class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default='TRUE', nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
```
`models.Base.metadata.create_all(bind=engine)` creates any tables that do not already exist, based on these class definitions. It will not alter a table that already exists, so adding a new column to a model later does not retroactively update existing rows. This is why old rows created before `created_at` existed showed `null` for that field, even though new rows got a real timestamp.

### Query methods learned

Get all rows:
```python
db.query(models.Post).all()
```

Get one row by id:
```python
db.query(models.Post).filter(models.Post.id == id).first()
```
`.filter()` builds the WHERE clause. `.first()` adds a LIMIT 1 to the SQL so Postgres stops scanning once it finds a match, and returns `None` if nothing matches.

Create a row:
```python
new_post = models.Post(title=data.title, content=data.content, published=data.published)
db.add(new_post)
db.commit()
db.refresh(new_post)
```
* `db.add()` stages the new object in the session.
* `db.commit()` writes it to the database.
* `db.refresh()` reloads the object with anything the database generated, like the auto incremented `id` and the `created_at` default. This is the SQLAlchemy equivalent of `RETURNING *` in raw SQL.

Shortcut for passing fields:
```python
new_post = models.Post(**data.model_dump())
```
`model_dump()` turns the Pydantic object into a dict. The double star unpacks that dict into individual keyword arguments, since the model constructor expects `title=..., content=..., published=...` rather than a single dict. This only works cleanly if every key in the dict matches an actual column on the model, otherwise it throws an error immediately, which is actually useful for catching mismatches early.

Delete a row:
```python
post = db.query(models.Post).filter(models.Post.id == id).first()
db.delete(post)
db.commit()
```
`db.delete()` is a session method, not a method on the row object itself.

Update rows:
```python
db.query(models.Post).filter(models.Post.id == id).update(data.model_dump(), synchronize_session=False)
db.commit()
```
`.update()` expects a dictionary directly as its argument, so no double star unpacking is used here, unlike the constructor case above. It builds the SET clause from the dict's keys and values. It returns the number of rows matched and updated, not the updated object itself, so `if not update_post` is really checking "was the count zero," which doubles nicely as a 404 check. To actually return the updated row, you need a separate query afterward:
```python
updated = db.query(models.Post).filter(models.Post.id == id).first()
```
`synchronize_session=False` tells SQLAlchemy not to bother syncing this change with any Post objects already loaded in memory in the current session, which is faster when that syncing is not needed.

## Bugs encountered and what they taught

1. Passing a dict to `.update()` with a key that does not match any column on the model (for example a Pydantic field called `rating` with no matching column) caused `sqlalchemy.exc.CompileError: Unconsumed column names`. This is the same root issue the double star unpacking would catch earlier, as a `TypeError`, when used on a constructor instead.
2. Calling `post.delete(post)` failed because `.delete()` belongs to the session (`db`), not to the row object. The session is what talks to the database, the row object is just data.
3. Including `created_at` as an optional field on the request body schema meant an update request that did not send `created_at` would default it to `None`, and `.update()` would then overwrite the real timestamp with null. Fields the client should never set, like `created_at` or `id`, should not exist on the request schema at all.
4. `not post` and `post is None` behave identically when `post` can only ever be a model instance or `None`, since model instances are always truthy. They differ for genuinely falsy non None values like `0` or `""`, so `is None` is the more precise way to write the intent when checking query results.

## Pydantic schemas and response models
 
Schemas were split using inheritance instead of duplicating fields across separate unrelated classes:
```python
class PostBase(BaseModel):
    title: str
    content: str
    published: bool = True
 
class CreatePost(PostBase):
    pass
 
class UpdatePost(PostBase):
    pass
 
class ResponseBase(PostBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```
* `PostBase` holds the fields every variant shares.
* `CreatePost` and `UpdatePost` are request schemas, only fields the client should ever send. They deliberately exclude `id` and `created_at`, since the client never sets those.
* `ResponseBase` is a response schema, it adds `id` and `created_at` on top of the shared base, since those exist on the actual database row and are useful for the client to receive back, even though the client never sent them.
* `model_config = ConfigDict(from_attributes=True)` tells Pydantic it is allowed to build this schema by reading attributes directly off an object (like `new_post.title`), not just from a dict. Without this, returning a raw SQLAlchemy model instance from a route would fail validation, since Pydantic by default expects dict like input.
* `response_model=schemas.ResponseBase` on a route filters and validates the returned object down to exactly the fields declared on that schema, anything not declared there gets silently dropped from the response, even if the underlying object has it.
A bug caught from this: putting `created_at` on a request schema (rather than only the response schema) meant a client who didn't send `created_at` would have it default to `None`, and an update using that dict would overwrite the real timestamp with null. Fields the client should never control do not belong on request schemas at all.
 
 
## Authentication
 
### Why plaintext passwords are never stored
If the database is ever leaked or read by anyone with access, plaintext passwords would expose every user's real password immediately, and since many people reuse passwords across sites, this is a serious risk beyond just this one app. Instead, passwords are hashed before being stored.
 
### Hashing (bcrypt, via passlib)
A hash is a one way transformation, easy to compute in one direction, practically impossible to reverse. The same password always produces a related but unique hash output (bcrypt automatically incorporates a random salt, so the same password hashed twice produces two different looking hashes, which protects against precomputed lookup table attacks).
 
`utils.py` is where this lives:
* A hashing function (commonly named `hash(password)`) takes the plain password at signup and returns the bcrypt hash, which is what actually gets saved as `user.password` in the database. The real plaintext password is never stored anywhere.
* A verify function (`utils.verify(plain_password, hashed_password)`) is used at login. It does not reverse the hash, it re-hashes the entered password using the same scheme and checks whether the result matches the stored hash. This is why login checks call `verify`, not some kind of decode.
### Login route flow (auth.py)
```python
@router.post("/login", response_model=schemas.Token)
async def login_user(user_cred: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_cred.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials")
    if not utils.verify(user_cred.password, user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials")
    access_token = oauth2.create_access_token(data={'user_id': user.id})
    return {"access_token": access_token, "token_type": 'bearer'}
```
 
Key points:
* `OAuth2PasswordRequestForm` is a FastAPI built in dependency that expects form encoded data with exactly `username` and `password` fields (plus a few OAuth protocol fields like `grant_type`). Since this app logs in by email, the form's `.username` field is used to hold the email value, the name `username` is just the form's fixed field name, not a statement about what the value actually represents.
* Both failure cases, user not found and wrong password, raise the exact same error with the exact same status code and message. This is intentional. If the two cases returned different responses, an attacker could tell which emails are registered just by testing logins (account enumeration). Returning identical errors either way avoids leaking that information.
* `403 Forbidden` is used here rather than `404 Not Found`, since the login endpoint itself was found and worked fine, the credentials were what got rejected. `404` is reserved for when a specific requested resource genuinely does not exist (like `GET /posts/77` for a post id that was never created).
* On success, only `user.id` is placed inside the token payload, not the password or other sensitive fields, since anyone can decode a JWT's payload (it is signed, not encrypted).
## JWT (JSON Web Tokens)
 
### What a JWT actually is
A JWT is a signed string built from three parts: header, payload, and signature. The payload is just base64 encoded JSON, readable by anyone who has the token, no decryption needed. What can't be faked without the secret key is the signature. So a JWT proves "this payload was issued by someone holding the secret key and has not been altered since," it does not hide the payload's contents.
 
### Creating a token (oauth2.py)
```python
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
```
* `.copy()` avoids mutating the caller's original dict, since `to_encode.update(...)` modifies in place.
* `exp` is added directly into the payload dict before encoding, so the expiry travels inside the token itself.
* `jwt.encode()` takes the payload, the secret key, and a single algorithm (singular `algorithm`, since only one is used to sign) and produces the token string.
* `datetime.now(timezone.utc)` is used instead of plain `datetime.now()` so the expiry does not depend on the server's local timezone setting.
### Verifying a token (oauth2.py)
```python
def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get('user_id')
        if id is None:
            raise credentials_exception
        token_data = schemas.TokenData(id=id)
        return token_data
    except JWTError:
        raise credentials_exception
```
* `jwt.decode()` takes `algorithms` as a list (plural), even with only one entry, since the function is designed to accept several allowed algorithms in general, decode is more permissive by design than encode.
* `jwt.decode()` automatically checks the signature is valid and that `exp` has not passed. If either check fails, it raises `JWTError` on its own, this is why there is no manual expiry check anywhere in this function.
* `payload.get('user_id')` rather than `payload['user_id']` avoids a `KeyError` if the token is malformed or missing that key, returning `None` instead, which the next line checks for explicitly.
* `schemas.TokenData(id=id)` wraps the raw id string into a small Pydantic schema (`TokenData`, with just `id: Optional[str] = None`). This is mostly for consistency with how every other piece of data in the app flows through schemas, and it gives Pydantic a chance to validate the value.
* `credentials_exception` is passed in by the caller rather than constructed here, so this function stays generic and does not need to know exactly what status code or message the caller wants to use.
### Turning verification into a reusable dependency
```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')
 
def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={"WWW-Authenticate": "Bearer"}
    )
    return verify_access_token(token, credentials_exception)
```
* `OAuth2PasswordBearer(tokenUrl='login')` tells FastAPI where the login endpoint lives (used in the auto generated docs) and gives FastAPI a way to automatically extract the token from the `Authorization: Bearer <token>` header on incoming requests, so `token` already holds the raw string by the time the function body runs.
* `401 Unauthorized` is used here, rather than `403`, since this represents "you did not provide valid credentials to access this at all," the standard code for missing or invalid authentication. The `WWW-Authenticate: Bearer` header is the conventional signal telling clients what kind of credential is expected.
* This function is what gets attached to protected routes as a dependency.
### Protecting a route
```python
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ResponseBase)
async def create_post(data: schemas.CreatePost, db: Session = Depends(get_db), current_user: schemas.TokenData = Depends(oauth2.get_current_user)):
    ...
```
Adding `current_user: schemas.TokenData = Depends(oauth2.get_current_user)` to a route's parameters means FastAPI runs the whole verification chain (extract token, decode, validate) before the route body executes at all. If the token is missing, expired, or invalid, the request is rejected with `401` before any of the route's own logic runs. If it succeeds, `current_user.id` holds the logged in user's id, ready to be used for things like checking post ownership before allowing an update or delete.
 
### What a login session actually is here
There is no server side session storage in this setup (no session table, no server memory of "who is logged in"). Instead, this is stateless token based authentication:
1. Client logs in once, receives a signed token.
2. Client stores that token (commonly in memory or local storage on the frontend) and sends it back in the `Authorization` header on every subsequent request.
3. The server does not need to remember anything between requests, it just re-verifies the token's signature and expiry each time, using `get_current_user`.
4. "Logging out" in this model is mostly a frontend concept, just discarding the stored token, since the server has no session to destroy. The token remains technically valid until it expires on its own.

## Post ownership (authorization, not just authentication)

Authentication answers "who is this." Authorization answers "is this person allowed to do this specific thing." JWT verification (`get_current_user`) only handles the first part, so without an extra check, any logged in user could edit or delete any post, not just their own, just by guessing an id in the URL.

```python
@router.delete("/{id}", status_code=204)
async def delete_post(id: int, db: Session = Depends(get_db), current_user = Depends(oauth2.get_current_user)):
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.delete(post)
    db.commit()
```

The existence check and the ownership check are deliberately two separate `if` blocks, in that order, because they answer different questions and deserve different status codes. "Does this post exist at all" is `404`. "Does this post exist, but you don't own it" is `403`, the same forbidden code used for failed logins, since in both cases the server understood the request perfectly and is refusing it on purpose. Checking ownership before existence would mean leaking whether an id exists at all before confirming it's even real, so existence is checked first.

The same two checks were copied into `update_post`, since without it, `PUT /posts/{id}` had the identical hole, any logged in user could rewrite any post's title and content.

## Linking posts to users (foreign key + relationship)

### The column
```python
from sqlalchemy import ForeignKey

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    ...
```
`ForeignKey()` takes a string, `"users.id"`, not the `User` class itself. This is because of import order, `models.py` defines `Post` and `User` in the same file top to bottom, and writing `ForeignKey(User.id)` would require `User` to already be fully defined above `Post`, every time, in every file that ever needs this. The string form is resolved lazily by SQLAlchemy later, once all models are loaded, so the two classes don't need to know about each other's definition order at all.

`nullable=False` means a post genuinely cannot exist without an owner, matching how posts actually get created, there's no code path that creates a post without a logged in user attached.

### The relationship
```python
from sqlalchemy.orm import relationship

class Post(Base):
    ...
    owner = relationship("User")
```
This adds no column to the table, it is a pure Python/ORM convenience. `owner_id` is the real, stored, queryable integer. `owner` is a virtual attribute that, when accessed (`post.owner`), tells SQLAlchemy to go fetch the matching `User` row using `owner_id` behind the scenes, so `post.owner.email` works without writing a manual join every single time. Same reasoning as `ForeignKey` for why `"User"` is a string rather than the class directly.

### Reflecting ownership in the response

`owner_id` was added only to `ResponseBase`, never to `PostBase`:
```python
class ResponseBase(PostBase):
    id: int
    created_at: datetime
    owner_id: int
    owner: UserOut
    model_config = ConfigDict(from_attributes=True)
```
This was a deliberate repeat of the same lesson learned earlier with `created_at` on request schemas, `owner_id` is something the server decides, from the logged in user's token, never something the client should be allowed to send in the request body. Putting it on `PostBase` (which `CreatePost` inherits from) would mean a client could pass any `owner_id` they wanted and effectively create a post under someone else's name, since nothing downstream would reject it.

`owner: UserOut` works because `from_attributes=True` lets Pydantic walk `post.owner.email`, `post.owner.id` etc. directly off the SQLAlchemy object graph, the same mechanism that already let `ResponseBase` read plain attributes like `post.title`.

Creating the post now sets the owner explicitly:
```python
new_post = models.Post(owner_id=current_user.id, **data.model_dump())
```
`current_user.id` and `**data.model_dump()` can sit side by side in the same constructor call because there's no key collision between them, `data.model_dump()` only ever produces `title`, `content`, `published`, never `owner_id`, since it was deliberately kept off `CreatePost`.

## Query parameters

Any function parameter on a route that is not a path parameter (not inside `{}`) and not a Pydantic model is automatically read by FastAPI from the URL's query string.

```python
@router.get("/", response_model=list[schemas.PostOut])
async def get_posts(db: Session = Depends(get_db),
                     current_user = Depends(oauth2.get_current_user),
                     limit: int = 10,
                     skip: int = 0,
                     search: Optional[str] = ""):
```
`limit` and `skip` together implement pagination, `LIMIT` caps how many rows come back, `OFFSET` (via `.offset(skip)`) skips past however many rows were already seen on previous pages. `search` defaults to an empty string rather than `None` specifically because `.contains("")` matches every row, giving "no filter" behavior for free without needing a separate branch to handle the unfiltered case.

## Counting votes with a join

Goal: each post's vote count, in one query, rather than running a separate count query per post (an N+1 query pattern, one extra round trip to the database per post returned).

```python
from sqlalchemy import func

results = db.query(models.Post, func.count(models.Vote.post_id).label("Votes")).join(
    models.Vote, models.Vote.post_id == models.Post.id, isouter=True
).group_by(models.Post.id).filter(models.Post.title.contains(search)).limit(limit).offset(skip).all()
```
* `func.count(...)` is a SQL aggregate, computed by the database, not by pulling rows into Python and counting there.
* `.label("Votes")` names this computed column. The exact string given here has to match a field name on the schema used to parse the result (below), since that's literally how Pydantic finds it.
* `isouter=True` makes this a LEFT OUTER JOIN rather than the default inner join. This matters specifically for posts with zero votes, an inner join only returns rows that have at least one match on both sides, so a post with no votes at all would simply vanish from the results instead of showing a count of 0.
* `.group_by(models.Post.id)` is required any time an aggregate function (`func.count`) is selected alongside non-aggregated columns (the full `Post` row), the database needs an explicit grouping to know which rows to count together.

### Response_model expecting a flat object, getting a tuple

`db.query(models.Post, func.count(...))` selects two things, so each row that comes back is a `Row` object behaving like `(Post_instance, count)`, not a flat object with `.title` directly on it. Returning this against `response_model=list[schemas.ResponseBase]` produced 30 validation errors, every field on every row reported as "missing," since Pydantic was trying to read `.title`, `.id` etc. straight off a tuple-like object that doesn't have them at that level.

The fix was a new schema shaped to match what the row actually contains:
```python
class PostOut(BaseModel):
    Post: ResponseBase
    Votes: int
```
The field name `Post` matches the class name SQLAlchemy gives the row's first selected entity by default. The field name `Votes` matches the `.label("Votes")` given to the count column. Pydantic, given `from_attributes` behavior, can read named attributes off a `Row` the same way it reads them off a model instance, so naming the schema's fields to exactly match is what makes the parsing work.

## Votes feature (many to many via a join table)

A user can vote on many posts, a post can receive votes from many users, this is a many to many relationship, modeled with a separate table that holds pairs of foreign keys rather than adding columns to either `Post` or `User` directly.

```python
class Vote(Base):
    __tablename__ = "votes"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
```
There is no separate `id` column here, `user_id` and `post_id` together form a composite primary key, meaning the database itself enforces that a given (user, post) pair can only ever appear once, exactly the constraint needed so a user can't vote on the same post twice. `ondelete="CASCADE"` means if the referenced user or post is ever deleted, any vote rows pointing at it are deleted automatically too, instead of being left behind as orphaned rows referencing something that no longer exists.

```python
from pydantic import conint

class Vote(BaseModel):
    post_id: int
    dir: conint(ge=0, le=1)
```
`conint(ge=0, le=1)` is a constrained integer, bounded on both sides, restricting `dir` to exactly `0` or `1`. An earlier version only set `le=1`, which let through `0`, `-1`, `-500`, anything at or below 1, since `le` alone only bounds one side.

### The route, four cases

```python
@router.post("/", status_code=status.HTTP_201_CREATED)
async def vote_post(vote: schemas.Vote, db: Session = Depends(get_db), current_user = Depends(oauth2.get_current_user)):
    post = db.query(models.Post).filter(models.Post.id == vote.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    found_vote = db.query(models.Vote).filter(
        models.Vote.post_id == post.id, models.Vote.user_id == current_user.id
    ).first()

    if vote.dir == 1:
        if found_vote:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                 detail=f"user {current_user.id} has already voted on post {vote.post_id}")
        new_vote = models.Vote(post_id=vote.post_id, user_id=current_user.id)
        db.add(new_vote)
        db.commit()
        return {"message": "successfully added vote"}
    else:
        if not found_vote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vote does not exist")
        db.delete(found_vote)
        db.commit()
        return {"message": "successfully deleted vote"}
```
`dir == 1` means cast a vote, `dir == 0` means remove one, and each of those two cases has its own success path and its own failure path, four cases total. `409 Conflict` is used for "you already voted," since the request is well formed and the user is allowed to vote in general, the conflict is specifically that this exact (user, post) pair already exists. `404` is used for "no vote to remove," consistent with how `404` is used everywhere else in this project, for "the specific thing you're trying to act on doesn't exist."

