from sqlalchemy import Column,Boolean,String,Text,ForeignKey,Integer,UniqueConstraint,DateTime,func,Table
import uuid
from sqlalchemy.orm import relationship
from Database.database import Base
from sqlalchemy.dialects.postgresql import UUID
from pydantic import EmailStr
from datetime import datetime




class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4,index=True)

#Table for revoked Tokens
revoked_tokens = Table(
    "revoked_tokens",
    Base.metadata,
    Column('token', String, primary_key=True),
    Column('expires_at',DateTime,nullable=False)
)


class User(BaseModel):
    __tablename__ = "users"

    name = Column(String(50),unique=True,nullable=False,index=True)
    hashed_password = Column(String,nullable=False)
    email = Column(Text,unique=True,nullable=False,index=True)
    profile_picture = Column(String,nullable=True)
    description = Column(Text,nullable=True)
    token_version = Column(Integer,default=0,nullable=False)

    #Relationships with group   
    groups = relationship('Group',secondary="group_and_user_association",back_populates='users')
    
    #Relationship with request table
    request_sent = relationship("User",
                                secondary="join_requests",
                                primaryjoin="User.name == JoinRequest.from_name ",
                                secondaryjoin="User.name==JoinRequest.to_name ",
                                cascade="all,delete-orphan",
                                single_parent=True,
                                back_populates="request_received"
                                )

    request_received = relationship("User",
                                    secondary="join_requests",
                                    primaryjoin="User.name == JoinRequest.to_name",
                                    secondaryjoin="User.name == JoinRequest.from_name",
                                    back_populates="request_sent"
                                    )
    messages = relationship("HumanMessage",back_populates="sender",cascade="all,delete-orphan")

class AiAgent(BaseModel):
    __tablename__ = "ai_agents"

    name = Column(String(50),unique=True,nullable=False,index=True)
    description = Column(Text,nullable=True)
    prompt_template1 = Column(Text,nullable=True)
    prompt_template2 = Column(Text,nullable=True)
    #Relationships
    messages = relationship("AgentMessage",back_populates="sender",cascade="all,delete-orphan")
    groups = relationship("Group",secondary="group_and_agent_associations",back_populates="agents")

    

class Group(BaseModel):
    __tablename__ = "groups"
    name = Column(String(50),unique=True,nullable=False,index=True)
    admin_user = Column(UUID(as_uuid=True),ForeignKey('users.id',ondelete="CASCADE"))
    description = Column(Text,nullable=True)
    #Relationships
    humans_messages = relationship("HumanMessage",back_populates="message_belongs_to_group",cascade="all,delete-orphan",order_by= "HumanMessage.sent_at")
    agents_messages = relationship("AgentMessage",back_populates="message_belongs_to_group",cascade="all,delete-orphan",order_by="desc(AgentMessage.sent_at)")
    users = relationship("User",secondary="group_and_user_association",back_populates="groups")
    agents = relationship("AiAgent",secondary="group_and_agent_associations", back_populates="groups")



class GroupAndUser(BaseModel):
    __tablename__ = "group_and_user_association"

    group_id = Column(UUID(as_uuid=True),ForeignKey('groups.id',ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True),ForeignKey('users.id',ondelete="CASCADE"))
    #Avoid duplicate entries of (group, user)
    __table_args__ = (UniqueConstraint('group_id','user_id'),)




class GroupAndAgent(BaseModel):
    __tablename__ = "group_and_agent_associations"

    group_id = Column(UUID(as_uuid=True),ForeignKey("groups.id",ondelete="CASCADE"))
    agent_id = Column(UUID(as_uuid=True),ForeignKey("ai_agents.id",ondelete="CASCADE"))
    
    #Avoide duplicate entries of (group,ai_agent)
    __table_args__ = (UniqueConstraint("group_id","agent_id"),)

    

 
class HumanMessage(BaseModel):
    __tablename__ = "human_messages"

    message = Column(Text,nullable=False)
    user_id = Column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"))
    group_id = Column(UUID(as_uuid=True),ForeignKey("groups.id", ondelete="CASCADE"))
    sent_at = Column(DateTime(timezone=True),server_default=func.now())

    sender = relationship("User",back_populates="messages")
    message_belongs_to_group = relationship("Group",back_populates="humans_messages")


class AgentMessage(BaseModel):
    __tablename__ = "model_messages"

    message = Column(Text,nullable=False)
    group_id = Column(UUID(as_uuid=True),ForeignKey("groups.id", ondelete="CASCADE"))
    agent_id = Column(UUID(as_uuid=True),ForeignKey("ai_agents.id",ondelete="CASCADE"))
    sent_at = Column(DateTime(timezone=True),server_default=func.now())
    
    sender = relationship("AiAgent",back_populates="messages")
    message_belongs_to_group = relationship("Group",back_populates="agents_messages")

    

class JoinRequest(BaseModel):
    __tablename__ = "join_requests"

    from_name = Column(String,ForeignKey("users.name",ondelete="CASCADE"))
    to_name = Column(String,ForeignKey("users.name",ondelete="CASCADE"))
    group_name = Column(String,ForeignKey("groups.name",ondelete="CASCADE"))
    accepted = Column(Boolean,default=False)

    __table_args__ = (UniqueConstraint("to_name","group_name"),)

