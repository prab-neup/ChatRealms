from fastapi import APIRouter,Depends,HTTPException,status
from Schemas.db_schemas import GetUsers,RegisterUser,RegisterGroup,GetTheUser
from Database.database import db_session,get_db
from auth import get_current_user,get_user,get_password_hash,authenticate_user,create_access_token
from Models.models import User
from fastapi.security import OAuth2PasswordRequestForm 
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

public_router = APIRouter()


@public_router.get('/hello')
async def say_hello():
    return {"message":"Hello Everyone!!"}



@public_router.post('/register',response_model=GetUsers)
async def create_user(user:RegisterUser,db:db_session):
    if_exists = await get_user(db,user.name)
    if if_exists:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="User with that name already exists.")
    new_user = User(name = user.name,email= user.email,hashed_password = get_password_hash(user.password),description=user.description)
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500,detail="Database Error.")


class Token(BaseModel):
    access_token: str
    token_type: str

@public_router.post("/login", response_model=Token  )
async def login_for_token(db:AsyncSession = Depends(get_db),form_data:OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(username=form_data.username,password=form_data.password,db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires  = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES",60)))
    access_token = create_access_token(data={'username':user.name,"token_version":user.token_version},expires_delta=access_token_expires)
    return {"access_token":access_token,"token_type":"bearer"}









