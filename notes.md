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

