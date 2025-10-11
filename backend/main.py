import os
import pycountry
import traceback
import re
from countryinfo import CountryInfo
from geopy.geocoders import Nominatim
from mistralai import Mistral
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ItineraryRequest(BaseModel):
    country: str
    days: int
    interests: List[str]
    arrivalDate: str  # YYYY-MM-DD

class ItineraryResponse(BaseModel):
    itinerary: str

MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_KEY:
    raise RuntimeError("MISTRAL_API_KEY not found in env vars")
client = Mistral(api_key=MISTRAL_KEY)

SYSTEM_PROMPT = """You are an experienced travel planner.

Your output must follow this exact structure:

1. Climate Summary  
2. Day-by-Day Itinerary  
3. Packing List

Each section should be clearly labeled.  

- Use bullet points for each day's itinerary.
- Include practical tips (transport, best neighbourhoods, local dishes).
- Packing list should be a single list covering the entire trip, based on the climate and activities.
- Do not include a packing list per day.
- Be friendly and concise."""



def build_user_prompt(country: str, days: int, interests: List[str], climate: str) -> str:
    interests_str = ", ".join(interests) if interests else "general sightseeing"
    return (
        f"Plan a {days}-day trip to {country} for someone interested in {interests_str}.\n"
        f"The expected climate during the trip is: {climate}.\n"
        f"Provide a day-by-day itinerary with activities, travel tips, and highlights.\n"
        f"At the end, include a single, comprehensive packing list that covers the entire trip based on the climate and activities.\n"
        f"Do not include a packing list per day."
    )


@app.post("/generate-itinerary", response_model=ItineraryResponse)
async def generate_itinerary(req: ItineraryRequest):
    try:
        # STEP 1: Generate initial itinerary without climate info
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(req.country, req.days, req.interests, "No climate data yet.")},
        ]

        response = client.chat.complete(
            model="mistral-tiny",
            messages=messages,
            temperature=0.5,
            max_tokens=1800,
        )

        initial_itinerary = response.choices[0].message.content.strip()

        # STEP 2: Extract cities and get detailed climate summary
        climate_summary = await build_citywise_climate_summary(initial_itinerary, req.country, req.arrivalDate)
        print("City-specific climate summary:", climate_summary)

        # STEP 3: Regenerate itinerary with real climate data
        final_prompt = build_user_prompt(req.country, req.days, req.interests, climate_summary)

        final_response = client.chat.complete(
            model="mistral-tiny",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.5,
            max_tokens=1800,
        )

        final_itinerary = final_response.choices[0].message.content.strip()
        return ItineraryResponse(itinerary=final_itinerary)

    except Exception as e:
        print("Backend error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


geolocator = Nominatim(user_agent="travel-app")

def get_country_coords(country_name: str):
    try:
        country = pycountry.countries.lookup(country_name)
        ci = CountryInfo(country.name)

        capital = ci.capital()
        latlon = ci.info().get("latlng")

        if latlon and len(latlon) == 2:
            return {"lat": latlon[0], "lon": latlon[1], "capital": capital}

        location = geolocator.geocode(f"{capital}, {country.name}")
        if location:
            return {"lat": location.latitude, "lon": location.longitude, "capital": capital}

    except Exception as e:
        print(f"Error finding coordinates for {country_name}: {e}")
        return None

async def get_climate_info(country: str, arrivalDate: str) -> str:
    import datetime
    import httpx

    coords = get_country_coords(country)
    if not coords:
        return "Climate data unavailable"

    try:
        date_obj = datetime.datetime.strptime(arrivalDate, "%Y-%m-%d")
        end_date = date_obj + datetime.timedelta(days=6)  # Assuming 1-week trip
        start_date_str = f"2022-{date_obj.month:02d}-{date_obj.day:02d}"
        end_date_str = f"2022-{end_date.month:02d}-{end_date.day:02d}"

        url = (
            f"https://historical-forecast-api.open-meteo.com/v1/forecast?"
            f"latitude={coords['lat']}&longitude={coords['lon']}"
            f"&start_date={start_date_str}&end_date={end_date_str}"
            f"&hourly=temperature_2m,precipitation"
            f"&temperature_unit=celsius&precipitation_unit=mm"
        )

        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()

        temperatures = data.get("hourly", {}).get("temperature_2m", [])
        precipitations = data.get("hourly", {}).get("precipitation", [])

        if temperatures and precipitations:
            avg_temp = sum(temperatures) / len(temperatures)
            total_rain = sum(precipitations)
            return (
                f"{coords['capital']} historical climate (based on 2022 data) "
                f"for your trip period: Avg temp {avg_temp:.1f}°C, total rainfall {total_rain:.1f} mm"
            )

    except Exception as e:
        print(f"Error fetching historical climate: {e}")

    # fallback
    date_obj = datetime.datetime.strptime(arrivalDate, "%Y-%m-%d")
    return get_generic_climate(country, date_obj.month)


def get_generic_climate(country_name: str, month: int) -> str:
    if month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    else:
        season = "autumn"
    return f"Generally {season} conditions, with moderate temperatures and occasional rainfall."

def extract_cities(itinerary_text: str, country: str) -> List[str]:
    pattern = re.compile(r'Day \d+: (.*?)\n', re.IGNORECASE)
    matches = pattern.findall(itinerary_text)
    cities = []

    for match in matches:
        if ',' in match:
            match = match.split(',')[0]
        city = match.strip()
        if city and city.lower() != country.lower():
            cities.append(city)

    return list(set(cities))  # Unique cities

def get_city_coords(city: str, country: str):
    try:
        location = geolocator.geocode(f"{city}, {country}")
        if location:
            return {"city": city, "lat": location.latitude, "lon": location.longitude}
    except Exception as e:
        print(f"Failed to get location for {city}, {country}: {e}")
    return None

async def get_city_climate(lat: float, lon: float, arrivalDate: str) -> str:
    import datetime
    import httpx

    try:
        date_obj = datetime.datetime.strptime(arrivalDate, "%Y-%m-%d")
        end_date = date_obj + datetime.timedelta(days=6)
        start_date_str = f"2022-{date_obj.month:02d}-{date_obj.day:02d}"
        end_date_str = f"2022-{end_date.month:02d}-{end_date.day:02d}"

        url = (
            f"https://historical-forecast-api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&start_date={start_date_str}&end_date={end_date_str}"
            f"&hourly=temperature_2m,precipitation"
            f"&temperature_unit=celsius&precipitation_unit=mm"
        )

        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()

        temps = data.get("hourly", {}).get("temperature_2m", [])
        rain = data.get("hourly", {}).get("precipitation", [])
        if temps and rain:
            avg_temp = sum(temps) / len(temps)
            total_rain = sum(rain)
            return f"Avg temp: {avg_temp:.1f}°C, Rainfall: {total_rain:.1f} mm"

    except Exception as e:
        print(f"Error fetching weather for city: {e}")

    return "Climate data unavailable"

async def build_citywise_climate_summary(itinerary_text: str, country: str, arrivalDate: str):
    cities = extract_cities(itinerary_text, country)
    summaries = []

    for city in cities:
        coords = get_city_coords(city, country)
        if coords:
            climate = await get_city_climate(coords['lat'], coords['lon'], arrivalDate)
            summaries.append(f"{city}: {climate}")
        else:
            summaries.append(f"{city}: Climate data unavailable")

    return "\n".join(summaries)
