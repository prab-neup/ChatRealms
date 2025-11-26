from fastapi import APIRouter , Depends,HTTPException,status,Response

from auth import get_current_user,get_user,get_group,get_password_hash,verify_password,oauth2_scheme
from Schemas.db_schemas import GetUsers,RegisterUser,RegisterGroup,SendRequest,GetTheUser,AddToHumanGroup,OutRequest,ChangePassword,GetGroup,SetAI,GetAiAgent
from Database.database import db_session
from Models.models import User , Group,GroupAndUser,JoinRequest,revoked_tokens,GroupAndUser,AiAgent,GroupAndAgent
from typing import List
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select,insert,delete
from sqlalchemy.orm import selectinload
from dotenv import load_dotenv
from datetime import datetime
import os
from jose import JWTError,jwt

load_dotenv()

protected_router = APIRouter(
                            dependencies=[Depends(get_current_user)]
                            )




@protected_router.get("/users/me",response_model=GetTheUser)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user




@protected_router.get("/users/",response_model=List[GetUsers])
async def get_users(db:db_session):
    try:
        query = select(User)
        result = await db.execute(query)
        users = result.scalars().all()
        if not users:
            raise HTTPException(status_code=404,detail="No user found")
        return users
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500,detail="Databse error")






@protected_router.post('/add_agent')
async def set_agent(ai:SetAI,db:db_session):
    try:
        stmt = AiAgent(name=ai.name,description=ai.description,prompt_template1=ai.prompt_template1,prompt_template2=ai.prompt_template2)
        db.add(stmt)
        await db.commit()
        return Response(status_code=status.HTTP_201_CREATED,content="Agent added successfully.")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500,detail="Database Error.")






@protected_router.get('/agents',response_model=List[GetAiAgent])
async def get_agents(db:db_session):
    try:
        stmt = select(AiAgent)
        agents = await db.execute(stmt)
        agents = agents.scalars().all()
        if not agents:
            raise HTTPException(status_code=404,detail= "No ai found")
        return agents
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500,detail="Database Error.")



@protected_router.get('/delete/agent/{agent_name}')
async def delete_agent(agent_name:str,db:db_session):
    try:
        stmt = delete(AiAgent).where(AiAgent.name==agent_name)
        result = await db.execute(stmt)
        if result.rowcount ==0:
            raise HTTPException(status_code=404,detail="No such agent found.")
        await db.commit()
        return Response(status_code=status.HTTP_200_OK,content="Agent deleted successfully.")
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500,detail="Database Error.")
    

@protected_router.post('/assign_agent/{agent_name}/to_group/{group_name}')
async def assign_agent_to_group(agent_name:str,group_name:str,db:db_session):
    try:
        
        agent = await db.execute(select(AiAgent).where(AiAgent.name==agent_name))
        agent = agent.scalars().first()
        if not agent:
            raise HTTPException(status_code=404,detail="Agent not found.")
        group = await db.execute(select(Group).where(Group.name==group_name))
        group = group.scalars().first()
        if not group:
            raise HTTPException(status_code=404,detail="Group not found.")
        association = GroupAndAgent(group_id=group.id,agent_id=agent.id)
        db.add(association)
        await db.commit()
        return Response(status_code=status.HTTP_201_CREATED,content="Agent assigned to group successfully.")
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500,detail="Database Error.")



@protected_router.post('/add_group')
async def create_group(group:RegisterGroup,db:db_session,current_user:User = Depends(get_current_user)):
    try:
        new_group = Group(name=group.name,admin_user = current_user.id ,description=group.description)
        db.add(new_group)
        await db.commit()
        await db.refresh(new_group)
        add_admin = GroupAndUser(group_id=new_group.id,user_id=current_user.id)
        db.add(add_admin)
        await db.commit()
        return Response(status_code=status.HTTP_201_CREATED)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500,detail="Database Error.")



@protected_router.get("/group/users/{group_name}",response_model=List[GetTheUser])
async def get_group_users(group_name:str,db:db_session):
    try:
        group = await get_group(db,group_name)
        if not group:
            raise HTTPException(status_code=404,detail="Group not found.")
        stmt = (
            select(User)
            .join(GroupAndUser)
            .where(GroupAndUser.group_id == group.id)
        )
        
        result = await db.execute(stmt)
 
        users = result.scalars().all()
        if not users:
            raise HTTPException(status_code=404,detail="No users found in this group.")
        return users
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500,detail="Database Error.")



@protected_router.get("/agent/{group_name}")
async def get_group_details(group_name:str,db:db_session):
    try:
        group = await get_group(db,group_name)
        if not group:
            raise HTTPException(status_code=404,detail="Group not found.")
        stmt = (
            select(AiAgent)
            .join(GroupAndAgent)
            .where(GroupAndAgent.group_id == group.id)
        )
        result = await db.execute(stmt)
        agent = result.scalars().first()
        if not agent:
            raise HTTPException(status_code=404,detail="No agent assigned to this group.")
        return {"agent":agent.name,"description":agent.description}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500,detail="Database Error.")
    
    

#Can be improved
@protected_router.post("/send_request")
async def send_join_request(sent_request:SendRequest,db:db_session,current_user:User = Depends(get_current_user)):
    try:
        to_user = await get_user(db,sent_request.to_name)
        group = await get_group(db,sent_request.group_name)
        if not to_user :
            raise HTTPException(status_code=404,detail="User not found.")
        if not group:
            raise HTTPException(status_code=404,detail="Group not found.")
        request = JoinRequest(from_name=current_user.name,to_name=to_user.name,group_name = group.name)
        try:
            db.add(request)
            await db.commit()
            await db.refresh(request)
            return Response(status_code=status.HTTP_201_CREATED)
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500,detail="Database Error.")
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Database Error.")







@protected_router.get("/requests",response_model=List[OutRequest])
async def get_all_requests(db:db_session,current_user:User = Depends(get_current_user)):
    all_requests = select(JoinRequest).where(JoinRequest.to_name == current_user.name)
    try:
        result = await db.execute(all_requests)
        requests =  result.scalars().all()
        if not requests:
            return Response(status_code=status.HTTP_200_OK,content="No requests found.",media_type="text/plain")
        return requests
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Databse Error.")


    




@protected_router.post("/respond_to_request")
async def respond_to_request(decision:AddToHumanGroup,db:db_session,current_user:User=Depends(get_current_user)):
    if decision.response:
        try:
            group = await get_group(db,decision.group_name)
            if not group:   
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Group not found.")
            new_member = GroupAndUser(group_id = group.id,user_id=current_user.id)
            request = await db.execute(delete(JoinRequest).where(JoinRequest.to_name==current_user.name , JoinRequest.group_name==group.name))
            if request.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="No such request found.")

            db.add(new_member)
            await db.commit()

            await db.refresh(new_member)      
            return Response(content="Request accepted.",media_type="text/plain",status_code=status.HTTP_200_OK)
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error.")
       
    else:
        try:
            stmt = delete(JoinRequest).where(JoinRequest.to_name==current_user.name , JoinRequest.group_name==decision.group_name)
            result = await db.execute(stmt)
            if result.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="No such request found.")
            await db.commit()
            return Response(status_code=status.HTTP_200_OK,content="Request deleted.")
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error.")

    
    






@protected_router.post("/change-password")
async def change_password(password_data:ChangePassword,db:db_session,current_user:User = Depends(get_current_user)):
    is_valid = verify_password(password_data.current_password,current_user.hashed_password)
    if is_valid:
        current_user.hashed_password = get_password_hash(password_data.new_password)
        current_user.token_version = (current_user.token_version + 1)%100
        try:
            db.add(current_user)

            await db.commit()
            await db.refresh(current_user)
            return Response(status_code=status.HTTP_200_OK,content="Password changed successfully.",media_type="text/plain")
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        await db.rollback()
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Supply correct password.")









@protected_router.get("/logout")
async def logout(db:db_session,current_user:User = Depends(get_current_user),token:str=Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token , os.getenv('SECRET_KEY') , algorithms=os.getenv('ALGORITHM'))
        expires_at = datetime.fromtimestamp(payload.get("exp"))
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Invalid Token")

    try:
        await db.execute(insert(revoked_tokens).values(token=token,expires_at = expires_at))
        await db.commit()
        return Response(status_code=status.HTTP_200_OK,content="Logged out successfully.",media_type="text/plain")
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error.")







@protected_router.get("/my_groups",response_model=List[GetGroup])
async def get_my_groups(db:db_session,user:User=Depends(get_current_user)):
    try:
        stmt = (
            select(Group)
            .join(GroupAndUser)
            .where(GroupAndUser.user_id == user.id)
        )
        result = await db.execute(stmt)
        my_groups = result.scalars().all()
        if not my_groups:
            raise HTTPException(status_code=status.HTTP_204_NO_CONTENT,detail="You are not a member any group yet.")
        return my_groups
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Database error...")
