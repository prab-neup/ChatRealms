from pydantic import BaseModel,EmailStr
from sqlalchemy import UUID
from typing import Optional
from uuid import UUID
from typing import List


class RegisterUser(BaseModel):
    name:str
    email:EmailStr
    password:str
    description:Optional[str]

    class Config:
        orm_mode = True

class GetUsers(BaseModel):
    name:str
    description:Optional[str]

    class Config:
        orm_mode = True


class RegisterGroup(BaseModel):
    name:str
    description:Optional[str]

    class Config:
        orm_mode = True


class SendRequest(BaseModel):
    to_name:str
    group_name:str

    class Config:
        orm_mode = True




class GetTheUser(BaseModel):
    name:str
    email:EmailStr
    description:Optional[str]


    class Config:
        orm_mode = True


class OutRequest(BaseModel):
    from_name:str
    to_name:str
    group_name:str

    class Config:
        orm_mode = True

class AddToHumanGroup(BaseModel):
    group_name:str
    response:bool

class ChangePassword(BaseModel):
    current_password:str
    new_password:str





class SendMessage(BaseModel):
    message:str
    sender:str

    class Config:
        orm_mode = True

class GetGroup(BaseModel):
    name:str
    description:Optional[str]
    
    
class SetAI(BaseModel):
    name:str
    description:Optional[str]
    prompt_template1:Optional[str]
    prompt_template2:Optional[str]

    class Config:
        orm_mode = True
        
class GetAiAgent(BaseModel):
    name:str
    description:Optional[str]
    prompt_template1:Optional[str]
    prompt_template2:Optional[str]