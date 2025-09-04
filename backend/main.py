from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ItineraryRequest(BaseModel):
    country: str
    days: int
    interests: List[str]

@app.post("/generate-itinerary")
async def generate_itinerary(req: ItineraryRequest):
    # This is where you'll call the LLM for itinerary generation
    itinerary = f"Sample itinerary for {req.days} days in {req.country} focused on {', '.join(req.interests)}."
    return {"itinerary": itinerary}
