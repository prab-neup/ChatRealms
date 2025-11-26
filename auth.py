from passlib.context import CryptContext
from datetime import datetime,timedelta
from jose import ExpiredSignatureError, JWTError,jwt
from fastapi.security import OAuth2PasswordBearer     
from fastapi import Depends,HTTPException,status,WebSocket,WebSocketException
from dotenv import load_dotenv
from Database.database import db_session ,get_db
from sqlalchemy import select
from Models.models import User,Group,revoked_tokens
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional , List
import os
from pydantic import BaseModel





load_dotenv()



class TokenData(BaseModel):
    username:Optional[str] = None   


    
pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")  



def get_password_hash(password:str):
    return pwd_context.hash(password)



def verify_password(plain_password:str,hashed_password:str):
    return pwd_context.verify(plain_password,hashed_password)




async def get_user(db:AsyncSession,username:str):
    try:
        query = select(User).where(User.name==username)
        result = await db.execute(query)
        user = result.scalars().first()
        if not user:
            return False
        return user
    except SQLAlchemyError as e:
        return False  


async def get_group(db:AsyncSession,groupname):
    try:
        query = select(Group).where(Group.name == groupname)
        result = await db.execute(query)
        group = result.scalars().first()
        if not group:
            return False
        return group
    except SQLAlchemyError as e:
        return False


async def authenticate_user(username:str,password:str,db:AsyncSession):
    user = await get_user(db=db,username=username)
    if not user or not verify_password(password,user.hashed_password):
        return False
    return user




def create_access_token(data:dict, expires_delta:timedelta ):
    expire = datetime.utcnow() + expires_delta  
    data.update({'exp':expire})
    encoded_jwt = jwt.encode(data, os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM'))
    return encoded_jwt




async def get_current_user(db:db_session,token:str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Could not validate credentials.",headers={"WWW-Authenticate":"Bearer"},)
    try:
        #Check if token is revoked
        revoke_query = select(revoked_tokens).where(revoked_tokens.c.token == token)
        revoke_result = await db.execute(revoke_query)
        result =  revoke_result.fetchone() 
        if result:
            raise credentials_exception

        #Decode JWT
        payload = jwt.decode(token , os.getenv('SECRET_KEY')  , algorithms=os.getenv('ALGORITHM'))
        username:str = payload.get('username')
        token_version:int = payload.get('token_version')

        #Check if JWT is valid
        if username is None or token_version is None: 
            raise credentials_exception
        token_data = TokenData(username=username)


    except JWTError as e:
        raise credentials_exception

    #Fetch  and return the current user if all the above code ran successfully.
    user = await get_user(db=db,username=token_data.username)
    if user is None or user.token_version != token_version:
        raise credentials_exception
    return user

        

# import from jose import ExpiredSignatureError, JWTError

async def get_current_user_ws(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    token = websocket.query_params.get('token')
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return  # Just return after closing, no need to raise

    try:
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
        username: str = payload.get('username')
        token_version: int = int(payload.get('token_version'))
        
        if username is None or token_version is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token structure")
            return

        user = await get_user(username=username, db=db)  # Use username directly
        if user is None or user.token_version != token_version:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token or version")
            return
       
        return user

    except ExpiredSignatureError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token expired. Please log in again.")
        return
        
    except JWTError as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

        

    
