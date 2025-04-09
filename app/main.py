from fastapi import FastAPI # type: ignore
from app.api.endpoints import instances  

# Create the FastAPI application instance.
app = FastAPI()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Include the endpoints defined in the instances router.
app.include_router(instances.router)
