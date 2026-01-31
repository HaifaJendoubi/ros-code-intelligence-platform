from fastapi import FastAPI

app = FastAPI(title="ROS Code Intelligence API")

@app.get("/")
def read_root():
    return {"message": "Hello from ROS Code Intelligence Backend"}