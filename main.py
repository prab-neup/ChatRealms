from fastapi import FastAPI
from routes.protected_routes import protected_router
from routes.public_routes import public_router

from routes.websocket_route import ws_router

from fastapi.middleware.cors import CORSMiddleware





   



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*","https://chat-realms-five.vercel.app"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  
)

app.include_router(public_router, prefix="")
app.include_router(protected_router, prefix="/api")
app.include_router(ws_router,prefix="/ws")








# @app.get("/requests/{user_id}")
# async def get_requests(user_id:UUID,db:db_session):
#     try:
#         query = select(User).