from fastapi import APIRouter,Depends, status, HTTPException,Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from .. import schemas,models,utils,oauth2

router=APIRouter(tags=['Authentication'])

@router.post("/login",response_model=schemas.Token)
async def login_user(user_cred: OAuth2PasswordRequestForm=Depends(),db: Session =Depends(get_db)):
    # OAuth2PasswordRequestForm returns only 1 dict with 2 items,"{ username: and password:}, so when checking email, use .username insteadof .email
    user=db.query(models.User).filter(models.User.email==user_cred.username).first()
    if not user: # verifying if user exists
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Invalid credentials")
    
    if not utils.verify(user_cred.password,user.password):# verifying the password
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Invalid credentials")
    
    access_token=oauth2.create_access_token(data={'user_id':user.id})
    return {"access_token":access_token,"token_type":'bearer'}