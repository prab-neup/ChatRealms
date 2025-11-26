from routes.protected_routes import protected_router
from routes.public_routes import public_router
from fastapi import WebSocket,Depends,status , HTTPException,WebSocketDisconnect,APIRouter
from auth import get_current_user_ws
from pydantic import BaseModel
from typing import Dict , Set
import time
import random
from Database.database import db_session,AsyncSessionLocal,get_db
from auth import get_group,get_current_user
from Models.models import GroupAndUser,User,HumanMessage,Group,AgentMessage,AiAgent
from sqlalchemy import select,desc, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from Schemas.db_schemas import SendMessage,GetUsers
from routes.ai_response import AIClient
import json


ws_router = APIRouter(dependencies=[Depends(get_current_user_ws)])

class ConnectionManager():
    def __init__(self):
        self.group_connections: Dict[str,Set[WebSocket]]  = {}
        self.user_groups : Dict[str,Set[str]] = {}

    async def connect(self,websocket:WebSocket,group_name:str,user:str):
        await websocket.accept()
        if user not in self.user_groups:
            self.user_groups[user] = set()
        self.user_groups[user].add(group_name)
        if group_name not in self.group_connections:
            self.group_connections[group_name] = set()
        self.group_connections[group_name].add(websocket)



    async def disconnect(self,group_name:str,user:str,websocket:WebSocket):
        if group_name in self.group_connections:
            self.group_connections[group_name].remove(websocket)#remove the websocket passed as argument
            if not self.group_connections[group_name]:#if self.group_connections is empty i.e. None
                del self.group_connections[group_name]#deletes the "group_name":() as no sockets are present in "group_name"
        if user in self.user_groups and group_name in self.user_groups[user]:
            self.user_groups[user].remove(group_name)
            if not self.user_groups[user]:
                del self.user_groups[user]


    async def disconnect_all(self,websocket:WebSocket,user:str):
        if user in self.user_groups: 
            if self.user_groups[user]:#if self.user_groups is not empty
                for group in self.user_groups[user]:#select groups of the user one-by-one
                    if group in self.group_connections: # if selected group is in self.group_connection 
                        if websocket in self.group_connections[group]:
                            await websocket.close(code=status.WS_1008_POLICY_VIOLATION,reason="Session Invalidated.")
                            self.group_connections[group].remove(websocket)
                            if not self.group_connections[group]:
                                del self.group_connections[group]
            del self.user_groups[user]

    async def broadcast(self,sender:str,message:str,group_name:str):
        if group_name in self.group_connections:
            for websockets in self.group_connections[group_name]:
                await websockets.send_text(f"{sender}:{message}")
                
    async def ai_response(self,ai_name:str,ai_message:str,group_name:str):
        if group_name in self.group_connections:
            for websockets in self.group_connections[group_name]:
                await websockets.send_text(f"{ai_name}:{ai_message}")


manager = ConnectionManager()


def random_lag(min_seconds=1, max_seconds=5):
    sleep_time = random.uniform(min_seconds, max_seconds)
    print(f"Sleeping for {sleep_time:.2f} seconds...")
    time.sleep(sleep_time)



@ws_router.websocket("/chat/group/{group_name}")
async def websocket_group(group_name: str, websocket: WebSocket, current_user: User = Depends(get_current_user_ws), db: AsyncSession = Depends(get_db)):
    # Check if current_user is None (authentication failed)
    if current_user is None:
        # WebSocket should already be closed by get_current_user_ws, just return
        return
    
    try:
        # Check if the group exists
        group = await get_group(db, group_name)
        if not group:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No such group.")
            return
        
        # Check if the user is a member of the group
        query = select(GroupAndUser).where(GroupAndUser.group_id == group.id, GroupAndUser.user_id == current_user.id)
        result = await db.execute(query)
        record = result.scalars().first()
        if not record:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="You are not a member of this group yet.")
            return

    except SQLAlchemyError as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Database error...")
        return

    await manager.connect(websocket, group.name, current_user.name)
    all_messages = []

    try:
        # Create subqueries for human and agent messages
        query = select(Group).options(
            selectinload(Group.humans_messages).selectinload(HumanMessage.sender),
            selectinload(Group.agents_messages).selectinload(AgentMessage.sender),
            selectinload(Group.agents)
        ).where(Group.id == group.id)
        
        result = await db.execute(query)
        current_group = result.scalars().first()
        
        if not current_group:
            await manager.disconnect(group.name, current_user.name, websocket)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No such group found.")
            return
        
        # Send existing human messages
        if current_group.humans_messages:
            for msg in current_group.humans_messages:
                data = {
                    "sender": msg.sender.name,
                    "message": msg.message,
                    "sent_at": str(msg.sent_at),
                    "role":"user"
                }
                all_messages.append(data)
                await websocket.send_text(json.dumps(data))
        if current_group.agents_messages:   
            for agent_msg in current_group.agents_messages:
                data = {
                    "agent_name": agent_msg.sender.name,
                    "message": agent_msg.message,
                    "sent_at": str(agent_msg.sent_at),
                    "role": "assistant"
                }
                all_messages.append(data)
                await websocket.send_text(json.dumps(data))
        
        if all_messages:
            all_messages = sorted(all_messages, key=lambda x: x['sent_at'])
            if len(all_messages) > 5:
                all_messages = all_messages[-5:]

        while True:
            message: str = await websocket.receive_text()

            new_message = HumanMessage(message=message, user_id=current_user.id, group_id=group.id)
            db.add(new_message)
            await db.commit()
            await manager.broadcast(current_user.name, message, group.name)
            new_message_dict = {
                "sender": current_user.name,
                "message": message,
                "sent_at": str(new_message.sent_at),
                "role":"user"
            }
            all_messages.append(new_message_dict)
            if len(all_messages) > 5:
                all_messages.pop(0)
            
            # Ask AI agent for response
            if current_group.agents:
                context = "\n".join([f"-{msg['sender'] if msg["role"] == "user" else "assistant"}:{msg['message']}" for msg in all_messages])
                
                async with AIClient() as ai_client:
                    for agent in current_group.agents:
                        try:
                            random_lag(3,6)  
                            ai_response = await ai_client.get_ai_response(context,agent.prompt_template1, agent.prompt_template2)
                        except Exception as e:
                            print(f"Error getting AI response from agent {agent.name}: {e}")
                            continue
                        if not ai_response:
                            print(f"No response from AI agent {agent.name}")
                            continue
                        else:
                            ai_message = AgentMessage(message=ai_response, agent_id=agent.id, group_id=group.id)
                            all_messages.append({
                                "sender": agent.name,
                                "message": message,
                                "sent_at": str(new_message.sent_at),
                                "role":"assistant"
                            }
                            )
                            if len(all_messages) > 5:
                                all_messages.pop(0)
                            db.add(ai_message)
                            await db.commit()
                            await manager.ai_response(agent.name, ai_response, group.name)
                    
            

    except WebSocketDisconnect as e:
        await manager.disconnect(group.name, current_user.name, websocket)

        








        # query = select(Group).options(selectinload(Group.humans_messages).selectinload(HumanMessage.sender),selectinload(Group.agents_messages).selectinload(AgentMessage.sender),selectinload(Group.agents)).where(Group.id == group.id)
        # result  = await db.execute(query)
        # current_group = result.scalars().first()
        # if not current_group:
        #     await manager.disconnect(group.name,current_user.name,websocket)
        #     await websocket.close(code=status.WS_1008_POLICY_VIOLATION,reason="No such group found.")
        #     return
        # # Send existing human messages
        # for msg in current_group.humans_messages:
        #     data = {"sender":msg.sender.name,
        #             "message":msg.message,
        #             "sent_at":str(msg.sent_at)
        #             }
        #     await websocket.send_text(json.dumps(data))
        # for agent_msg in current_group.agents_messages:
        #     data = {
        #         "agent_name":agent_msg.sender.name,
        #         "message":agent_msg.message,
        #         "sent_at":str(agent_msg.sent_at)
        #     }
        #     await websocket.send_text(json.dumps(data))

    


